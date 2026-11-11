"""Find videos that are taking off, without a YouTube API key.

Uses YouTube's own search (via yt-dlp) filtered by upload period and sorted by
views, then reads each top result's publish time to rank by views per hour.
Channel monitoring reads each channel's public RSS feed.
"""

from __future__ import annotations

import time
import urllib.parse
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor

import httpx
import yt_dlp

# YouTube search "upload date" filter values; results are sorted by views.
PERIODS = {"hoje": 2, "semana": 3, "mes": 4, "ano": 5}


def _search_filter(period: str, reusable_only: bool) -> str:
    """YouTube's ``sp`` search parameter: sort by views, upload window, optional Creative Commons."""
    import base64

    filters = bytes([0x08, PERIODS.get(period, 3)]) + (bytes([0x30, 0x01]) if reusable_only else b"")
    return base64.b64encode(bytes([0x08, 0x03, 0x12, len(filters)]) + filters).decode()
DETAIL_LIMIT = 15


# Ask YouTube as a Brazilian viewer: Portuguese titles and Brazilian results
# instead of English auto-translations of US videos.
BRAZIL = {
    "extractor_args": {"youtube": {"lang": ["pt"]}},
    "http_headers": {"Accept-Language": "pt-BR,pt;q=0.9"},
    "geo_bypass_country": "BR",
    "no_warnings": True,
}
WIDER_PERIOD = {"hoje": "semana", "semana": "mes", "mes": "ano"}


def _details(video_id: str) -> dict:
    with yt_dlp.YoutubeDL({"quiet": True, "skip_download": True, "noplaylist": True, **BRAZIL}) as ydl:
        info = ydl.extract_info(f"https://www.youtube.com/watch?v={video_id}", download=False, process=False)
    return {
        "timestamp": info.get("timestamp"),
        "views": info.get("view_count"),
        "likes": info.get("like_count"),
        "license": info.get("license"),
    }


def search_trending(query: str, period: str = "semana", shorts_only: bool = False, reusable_only: bool = False) -> list[dict]:
    """Top videos for ``query`` in the period, ranked by views per hour. Blocking.

    ``reusable_only`` keeps Creative Commons videos; each result's own license
    is read from its page either way, so the badge never relies on the filter.
    """
    entries: list[dict] = []
    while True:
        sp = urllib.parse.quote(_search_filter(period, reusable_only))
        url = f"https://www.youtube.com/results?search_query={urllib.parse.quote(query)}&sp={sp}&hl=pt-BR&gl=BR&persist_gl=1&persist_hl=1"
        with yt_dlp.YoutubeDL({"quiet": True, "extract_flat": True, "playlistend": 40, **BRAZIL}) as ydl:
            result = ydl.extract_info(url, download=False)
        entries = [e for e in result.get("entries") or [] if e.get("id") and e.get("ie_key") in (None, "Youtube")]
        # Creative Commons uploads are rare; widen the window instead of showing nothing.
        if entries or not reusable_only or period not in WIDER_PERIOD:
            break
        period = WIDER_PERIOD[period]
    if shorts_only:
        entries = [e for e in entries if (e.get("duration") or 0) and e["duration"] <= 180]
    entries = entries[:DETAIL_LIMIT]
    with ThreadPoolExecutor(8) as pool:
        details = list(pool.map(lambda e: _safe(_details, e["id"]), entries))
    now = time.time()
    videos = []
    for entry, extra in zip(entries, details):
        views = extra.get("views") or entry.get("view_count") or 0
        timestamp = extra.get("timestamp")
        hours = max(1.0, (now - timestamp) / 3600) if timestamp else None
        videos.append({
            "id": entry["id"],
            "url": f"https://www.youtube.com/watch?v={entry['id']}",
            "title": entry.get("title") or "",
            "channel": entry.get("channel") or entry.get("uploader") or "",
            "channel_id": entry.get("channel_id"),
            "duration": entry.get("duration"),
            "views": views,
            "likes": extra.get("likes"),
            "published": timestamp,
            "views_per_hour": round(views / hours) if hours else None,
            "license": extra.get("license"),
            "reuse_allowed": "creative commons" in (extra.get("license") or "").lower(),
            "thumbnail": f"https://i.ytimg.com/vi/{entry['id']}/hqdefault.jpg",
        })
    return sorted(videos, key=lambda v: v["views_per_hour"] or 0, reverse=True)


def _safe(fn, *args) -> dict:
    try:
        return fn(*args)
    except Exception:
        return {}


def resolve_channel(text: str) -> dict:
    """Channel id and name from a channel link, @handle or video link. Blocking."""
    text = text.strip()
    if text.startswith("@"):
        text = f"https://www.youtube.com/{text}"
    elif not text.startswith("http"):
        text = f"https://www.youtube.com/@{text}"
    with yt_dlp.YoutubeDL({"quiet": True, "extract_flat": True, "playlistend": 1}) as ydl:
        info = ydl.extract_info(text, download=False)
    channel_id = info.get("channel_id") or (info.get("id") if str(info.get("id", "")).startswith("UC") else None)
    if not channel_id:
        raise ValueError("Não encontrei esse canal")
    return {"channel_id": channel_id, "name": info.get("channel") or info.get("uploader") or info.get("title") or channel_id}


def channel_feed(channel_id: str) -> list[dict]:
    """Latest uploads from a channel's public RSS feed (newest first). Blocking."""
    response = httpx.get(f"https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}", timeout=15)
    response.raise_for_status()
    ns = {"a": "http://www.w3.org/2005/Atom", "yt": "http://www.youtube.com/xml/schemas/2015", "media": "http://search.yahoo.com/mrss/"}
    root = ET.fromstring(response.content)
    videos = []
    for entry in root.findall("a:entry", ns):
        video_id = entry.findtext("yt:videoId", namespaces=ns)
        stats = entry.find("media:group/media:community/media:statistics", ns)
        videos.append({
            "id": video_id,
            "url": f"https://www.youtube.com/watch?v={video_id}",
            "title": entry.findtext("a:title", namespaces=ns) or "",
            "channel": entry.findtext("a:author/a:name", namespaces=ns) or "",
            "published": entry.findtext("a:published", namespaces=ns),
            "views": int(stats.get("views")) if stats is not None and stats.get("views") else None,
            "thumbnail": f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg",
        })
    return videos


def video_facts(url: str) -> dict:
    """Public facts about one posted video, plus how it compares to the channel's latest uploads. Blocking."""
    import statistics

    with yt_dlp.YoutubeDL({"quiet": True, "skip_download": True, "noplaylist": True, **BRAZIL}) as ydl:
        info = ydl.extract_info(url, download=False, process=False)
    hours = max(1.0, (time.time() - info["timestamp"]) / 3600) if info.get("timestamp") else None
    facts = {
        "id": info.get("id"),
        "url": info.get("webpage_url") or url,
        "title": info.get("title"),
        "description": (info.get("description") or "")[:800],
        "tags": (info.get("tags") or [])[:20],
        "duration": info.get("duration"),
        "views": info.get("view_count"),
        "likes": info.get("like_count"),
        "comments": info.get("comment_count"),
        "hours_online": round(hours) if hours else None,
        "channel": info.get("channel"),
        "subscribers": info.get("channel_follower_count"),
        "thumbnail": f"https://i.ytimg.com/vi/{info.get('id')}/hqdefault.jpg",
        "transcript": _caption_text(info)[:2500],
    }
    try:
        recent = [v for v in channel_feed(info["channel_id"]) if v.get("views") is not None and v["id"] != info.get("id")]
        if recent:
            facts["channel_median_views"] = int(statistics.median(v["views"] for v in recent))
            facts["channel_best"] = max(recent, key=lambda v: v["views"])["title"]
    except Exception:
        pass
    return facts


def _caption_text(info: dict) -> str:
    """Spoken text from the video's (auto) captions, when YouTube has them."""
    import re

    for source in (info.get("subtitles") or {}, info.get("automatic_captions") or {}):
        for lang in ("pt-BR", "pt", "pt-orig"):
            tracks = source.get(lang) or []
            track = next((t for t in tracks if t.get("ext") == "vtt"), None)
            if not track:
                continue
            try:
                vtt = httpx.get(track["url"], timeout=20).text
            except Exception:
                continue
            lines = [l.strip() for l in vtt.splitlines() if l.strip() and "-->" not in l and not l.startswith(("WEBVTT", "Kind:", "Language:", "NOTE"))]
            # Auto captions scroll: each cue repeats the previous line as plain
            # text and adds the new words with timing tags. Keep only new text.
            fresh = [l for l in lines if "<" in l] or lines
            out: list[str] = []
            for line in fresh:
                clean = re.sub(r"<[^>]+>", "", line).strip()
                if clean and (not out or out[-1] != clean):
                    out.append(clean)
            return " ".join(out)
    return ""
