"""Gerador de imagens LOCAL (gratis) com FLUX.1 schnell, em ETAPAS (ideia do usuario):
  1) codificador de texto  -> prepara os prompts de TODAS as cenas -> sai da memoria
  2) gerador (transformer)  -> cria todas as imagens "latentes"       -> sai da memoria
  3) decodificador (VAE)    -> transforma tudo em PNG                 -> sai da memoria
Cada etapa roda num processo proprio: a placa fica com uma parte por vez e libera tudo ao terminar.
Modelos em D:\\modelos_imagem (fora do Ollama, sem ComfyUI).

Uso: python imagem_local.py lote pedidos.json      (lista de {"prompt","saida","proporcao","seed"})
     python imagem_local.py "prompt" saida.png [16:9|9:16|1:1] [seed]
"""
import json, os, subprocess, sys, tempfile, time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config
os.environ.setdefault("HF_HOME", config.HF_HOME)
os.environ.setdefault("HF_HUB_OFFLINE", "1")
REPO, GGUF_REPO, GGUF = "black-forest-labs/FLUX.1-schnell", "city96/FLUX.1-schnell-gguf", "flux1-schnell-Q8_0.gguf"
TAMANHOS = {"16:9": (1344, 768), "9:16": (768, 1344), "1:1": (1024, 1024)}
PASSOS = 4


def log(m):
    print(f"   [imagem local] {m}", flush=True)


def disponivel():
    if sdxl_disponivel():
        return True
    try:
        from huggingface_hub import try_to_load_from_cache
        return isinstance(try_to_load_from_cache(GGUF_REPO, GGUF), str) and isinstance(try_to_load_from_cache(REPO, "model_index.json"), str)
    except Exception:
        return False


# ---------------------------------------------------------------- etapas (cada uma num processo)
def etapa_texto(trab):
    import torch
    from diffusers import FluxPipeline
    t = time.time()
    pipe = FluxPipeline.from_pretrained(REPO, transformer=None, vae=None, torch_dtype=torch.bfloat16)
    pipe.text_encoder.to("cuda"); pipe.text_encoder_2.to("cuda")
    pedidos = json.load(open(os.path.join(trab, "pedidos.json"), encoding="utf-8"))
    with torch.no_grad():
        for i, p in enumerate(pedidos):
            pe, ppe, _ = pipe.encode_prompt(p["prompt"], prompt_2=None, device="cuda", max_sequence_length=256)
            torch.save({"pe": pe.cpu(), "ppe": ppe.cpu()}, os.path.join(trab, f"txt{i}.pt"))
    log(f"etapa 1/3 texto: {len(pedidos)} prompts em {time.time() - t:.0f}s")


def etapa_imagem(trab):
    import torch
    from huggingface_hub import hf_hub_download
    from diffusers import FluxPipeline, FluxTransformer2DModel, GGUFQuantizationConfig
    t = time.time()
    tr = FluxTransformer2DModel.from_single_file(
        hf_hub_download(GGUF_REPO, GGUF), quantization_config=GGUFQuantizationConfig(compute_dtype=torch.bfloat16),
        torch_dtype=torch.bfloat16, config=REPO, subfolder="transformer").to("cuda")
    pipe = FluxPipeline.from_pretrained(REPO, transformer=tr, text_encoder=None, text_encoder_2=None,
                                        tokenizer=None, tokenizer_2=None, vae=None, torch_dtype=torch.bfloat16)
    log(f"etapa 2/3 gerador carregado em {time.time() - t:.0f}s")
    pedidos = json.load(open(os.path.join(trab, "pedidos.json"), encoding="utf-8"))
    for i, p in enumerate(pedidos):
        t1 = time.time()
        w, h = TAMANHOS.get(p.get("proporcao", "16:9"), TAMANHOS["16:9"])
        e = torch.load(os.path.join(trab, f"txt{i}.pt"))
        g = torch.Generator("cpu").manual_seed(int(p.get("seed") or i))
        with torch.no_grad():
            lat = pipe(prompt_embeds=e["pe"].to("cuda"), pooled_prompt_embeds=e["ppe"].to("cuda"), width=w, height=h,
                       num_inference_steps=PASSOS, guidance_scale=0.0, generator=g, output_type="latent").images
        torch.save({"lat": lat.cpu(), "w": w, "h": h}, os.path.join(trab, f"lat{i}.pt"))
        log(f"etapa 2/3 imagem {i + 1}/{len(pedidos)} em {time.time() - t1:.0f}s")


def etapa_decodificar(trab, dispositivo="cuda"):
    import torch
    from diffusers import AutoencoderKL, FluxPipeline
    from diffusers.image_processor import VaeImageProcessor
    t = time.time()
    dt = torch.bfloat16 if dispositivo == "cuda" else torch.float32
    vae = AutoencoderKL.from_pretrained(REPO, subfolder="vae", torch_dtype=dt).to(dispositivo)
    vae.enable_tiling()
    proc = VaeImageProcessor(vae_scale_factor=16)
    pedidos = json.load(open(os.path.join(trab, "pedidos.json"), encoding="utf-8"))
    for i, p in enumerate(pedidos):
        d = torch.load(os.path.join(trab, f"lat{i}.pt"))
        lat = FluxPipeline._unpack_latents(d["lat"], d["h"], d["w"], 8)
        lat = (lat / vae.config.scaling_factor) + vae.config.shift_factor
        with torch.no_grad():
            img = vae.decode(lat.to(dispositivo, dt)).sample
        proc.postprocess(img.float().cpu(), output_type="pil")[0].save(p["saida"])
    log(f"etapa 3/3 decodificacao ({dispositivo}): {len(pedidos)} imagens em {time.time() - t:.0f}s")


# ---------------------------------------------------------------- orquestracao
def _rodar(etapa, trab, *extra):
    r = subprocess.run([sys.executable, os.path.abspath(__file__), "_etapa", etapa, trab, *extra],
                       env={**os.environ, "PYTHONUNBUFFERED": "1", "MIOPEN_FIND_MODE": "FAST", "PYTORCH_HIP_ALLOC_CONF": "garbage_collection_threshold:0.6",
                            "PYTORCH_CUDA_ALLOC_CONF": "garbage_collection_threshold:0.6",
                            "HF_HUB_OFFLINE": "1", "TQDM_DISABLE": "1"})
    return r.returncode == 0


TRAVA = os.path.join(config.MODELOS, "placa_em_uso.lock")


def _travar_placa():
    """So UM processo usa a placa por vez (dois ao mesmo tempo corrompem as imagens). Espera a vez."""
    import msvcrt
    f = open(TRAVA, "a+")
    avisou = False
    while True:
        try:
            f.seek(0); msvcrt.locking(f.fileno(), msvcrt.LK_NBLCK, 1)
            return f
        except OSError:
            if not avisou:
                log("placa de video ocupada por outra tarefa - aguardando a vez..."); avisou = True
            time.sleep(5)


def gerar_lote(pedidos):
    """pedidos: [{"prompt","saida","proporcao","seed"}]. Devolve quantas imagens ficaram prontas."""
    if not pedidos:
        return 0
    trava = _travar_placa()
    try:
        return _gerar_lote(pedidos)
    finally:
        try:
            import msvcrt; trava.seek(0); msvcrt.locking(trava.fileno(), msvcrt.LK_UNLCK, 1)
        except OSError:
            pass
        trava.close()


def _gerar_lote(pedidos):
    trab = tempfile.mkdtemp(prefix="img_", dir=config.MODELOS)
    json.dump(pedidos, open(os.path.join(trab, "pedidos.json"), "w", encoding="utf-8"), ensure_ascii=False)
    if os.environ.get("MOTOR_IMAGEM", "rapido") != "flux" and sdxl_disponivel():
        import shutil
        try:
            # lotes de ate 12 por processo + reinicio automatico se a placa entrar em falha (imagens-lixo em ~3s)
            for tentativa in range(8):
                faltam = [p for p in pedidos if not os.path.exists(p["saida"])]
                if not faltam:
                    break
                json.dump(faltam[:12], open(os.path.join(trab, "pedidos.json"), "w", encoding="utf-8"), ensure_ascii=False)
                os.environ["LOTE_INI"], os.environ["LOTE_TOTAL"] = str(len(pedidos) - len(faltam)), str(len(pedidos))
                ok = _rodar("sdxl", trab)
                if not ok:
                    log("placa reiniciada (falha detectada ou erro) - continuando de onde parou...")
        finally:
            shutil.rmtree(trab, ignore_errors=True)
        return sum(os.path.exists(p["saida"]) for p in pedidos)
    try:
        if not _rodar("texto", trab):
            raise RuntimeError("etapa de texto falhou")
        if not _rodar("imagem", trab):
            raise RuntimeError("etapa de geracao falhou")
        if not _rodar("decodificar", trab, "cuda"):
            log("decodificacao na placa falhou - tentando no processador (mais lento, mas seguro)")
            if not _rodar("decodificar", trab, "cpu"):
                raise RuntimeError("etapa de decodificacao falhou")
    finally:
        import shutil
        shutil.rmtree(trab, ignore_errors=True)
    return sum(os.path.exists(p["saida"]) for p in pedidos)


# ---------------------------------------------------------------- motor RAPIDO (padrao): RealVisXL V5 Lightning
SDXL_REPO, SDXL_ARQ = "SG161222/RealVisXL_V5.0_Lightning", "RealVisXL_V5.0_Lightning_fp16.safetensors"
SDXL_TAM = {"16:9": (1344, 768), "9:16": (768, 1344), "1:1": (1024, 1024)}
NEGATIVO = ("text, watermark, logo, signature, cartoon, anime, 3d render, illustration, deformed, disfigured, "
            "bad anatomy, extra fingers, extra limbs, blurry, low quality, jpeg artifacts, duplicate person, clone, twins, "
            "oversaturated, oversharpened, halo, hdr, plastic skin, waxy face")


def sdxl_disponivel():
    try:
        from huggingface_hub import try_to_load_from_cache
        return isinstance(try_to_load_from_cache(SDXL_REPO, SDXL_ARQ), str)
    except Exception:
        return False


def etapa_sdxl(trab):
    """Um processo so: o modelo inteiro cabe na placa (7 GB) -> segundos por imagem."""
    import torch
    from huggingface_hub import hf_hub_download
    from diffusers import StableDiffusionXLPipeline, DPMSolverMultistepScheduler
    t = time.time()
    pipe = StableDiffusionXLPipeline.from_single_file(hf_hub_download(SDXL_REPO, SDXL_ARQ), torch_dtype=torch.float16,
                                                      config="stabilityai/stable-diffusion-xl-base-1.0")
    pipe.scheduler = DPMSolverMultistepScheduler.from_config(pipe.scheduler.config, use_karras_sigmas=True,
                                                             algorithm_type="sde-dpmsolver++")
    pipe.unet.to("cuda"); pipe.text_encoder.to("cuda"); pipe.text_encoder_2.to("cuda")
    vae = pipe.vae.to("cuda")  # fp16 + pedacos: ~1s por imagem (fp32 transbordava a placa: ~60s)
    vae.enable_tiling()
    # Compel: prompts longos sem corte em 77 tokens (a ficha inteira dos personagens chega ao modelo)
    comp = None
    try:
        from compel import Compel, ReturnedEmbeddingsType
        comp = Compel(tokenizer=[pipe.tokenizer, pipe.tokenizer_2], text_encoder=[pipe.text_encoder, pipe.text_encoder_2],
                      returned_embeddings_type=ReturnedEmbeddingsType.PENULTIMATE_HIDDEN_STATES_NON_NORMALIZED,
                      requires_pooled=[False, True], truncate_long_prompts=False)
    except Exception as e:
        log(f"compel indisponivel ({str(e)[:60]}) - usando prompt normal")
    # teto de memoria: com limite, o PyTorch reaproveita a placa em vez de "transbordar" para a RAM (o que travava o PC)
    torch.cuda.set_per_process_memory_fraction(float(os.environ.get("TETO_PLACA", "0.72")))
    log(f"modelo rapido carregado em {time.time() - t:.0f}s")
    pedidos = json.load(open(os.path.join(trab, "pedidos.json"), encoding="utf-8"))
    for i, p in enumerate(pedidos):
        t1 = time.time()
        w, h = SDXL_TAM.get(p.get("proporcao", "16:9"), SDXL_TAM["16:9"])
        g = torch.Generator("cuda").manual_seed(int(p.get("seed") or i))
        torch.cuda.empty_cache()
        q = MODOS.get(p.get("qualidade") or "cinematografico", MODOS["cinematografico"])
        txt = {"prompt": p["prompt"], "negative_prompt": NEGATIVO}
        if comp is not None:
            try:
                with torch.no_grad():
                    pe, pp = comp(p["prompt"]); ne, npp = comp(NEGATIVO)
                    vazio = comp("")[0]
                    while ne.shape[1] < pe.shape[1]: ne = torch.cat([ne, vazio], 1)  # iguala os tamanhos (blocos de 77)
                    while pe.shape[1] < ne.shape[1]: pe = torch.cat([pe, vazio], 1)
                txt = {"prompt_embeds": pe, "pooled_prompt_embeds": pp, "negative_prompt_embeds": ne, "negative_pooled_prompt_embeds": npp}
            except Exception as e:
                log(f"compel falhou ({str(e)[:60]}) - usando prompt normal")
        lat = pipe(**txt, width=w, height=h, num_inference_steps=q["passos"],
                   guidance_scale=q["forca"], generator=g, output_type="latent").images
        torch.cuda.synchronize()
        t_ger = time.time() - t1
        if t_ger < MIN_GERAR_S:  # impossivel gerar uma imagem real tao rapido: a placa entrou em falha
            log(f"FALHA DA PLACA detectada (imagem em {t_ger:.1f}s) - descartando e reiniciando")
            sys.exit(3)
        with torch.no_grad():
            im = vae.decode(lat.to(vae.dtype) / vae.config.scaling_factor).sample
        img = pipe.image_processor.postprocess(im.float(), output_type="pil")[0]
        if q["rosto"] and p.get("rosto", True):
            t2 = time.time()
            try:
                img, n = refinar_rostos(pipe, vae, img, p["prompt"], g)
                tr = time.time() - t2
                if n: log(f"   {n} rosto(s) refeito(s) em {tr:.1f}s")
                if n and tr / n < MIN_ROSTO_S:
                    log(f"FALHA DA PLACA detectada no rosto ({tr / n:.1f}s/rosto) - descartando e reiniciando")
                    sys.exit(3)
            except Exception as e:
                log(f"refino de rosto pulado: {str(e)[:80]}")
        tmp = p["saida"] + ".tmp.png"
        img.save(tmp); os.replace(tmp, p["saida"])
        del lat, im
        torch.cuda.empty_cache()  # devolve a memoria da placa a cada imagem (evita transbordar para a RAM e ficar 6x mais lento)
        ini, tot = int(os.environ.get("LOTE_INI", 0)), int(os.environ.get("LOTE_TOTAL", 0)) or len(pedidos)
        print(f"PROGRESSO {ini + i + 1}/{tot}", flush=True)  # progresso do video inteiro (nao so do lote de 12)
        log(f"imagem {i + 1}/{len(pedidos)} em {time.time() - t1:.1f}s")


MIN_GERAR_S, MIN_ROSTO_S = 4.5, 4.0  # medido: imagem real >= ~8s, rosto real >= ~15s; lixo da placa em falha ~3s / ~0.6s


# modos de qualidade (medidos na RX 9060 XT, 1344x768): rapido ~8s | equilibrado ~8s + ~5s/rosto | cinematografico ~20s + rostos
MODOS = {"rapido": {"passos": 6, "forca": 1.0, "rosto": False},
         "equilibrado": {"passos": 8, "forca": 1.0, "rosto": True},
         "cinematografico": {"passos": 8, "forca": 1.2, "rosto": True}}  # forca>1 liga o prompt negativo (menos clones/defeitos), 2x mais lento


ROSTO_MODELO = config.ROSTO
_i2i = None


def refinar_rostos(pipe, vae, img, prompt, g):
    """'Detalhador de rosto': acha cada rosto, refaz so ele em alta resolucao (olhos/pele) e cola de volta suavemente."""
    global _i2i
    import numpy as np, cv2, torch
    from PIL import Image, ImageDraw, ImageFilter
    if not os.path.exists(ROSTO_MODELO):
        return img, 0
    W, H = img.size
    bgr = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)
    det = cv2.FaceDetectorYN.create(ROSTO_MODELO, "", (W, H), 0.6)
    rostos = det.detect(bgr)[1]
    if rostos is None:
        return img, 0
    n = 0
    if _i2i is None:
        from diffusers import StableDiffusionXLImg2ImgPipeline
        _i2i = StableDiffusionXLImg2ImgPipeline(**pipe.components)
    for x, y, w, h in [r[:4] for r in rostos][:4]:
        if w < 20:
            continue
        lado = int(min(max(w, h) * (2.0 if h < H * 0.4 else 1.35), W, H))
        cx, cy = x + w / 2, y + h / 2
        x0, y0 = int(max(0, min(W - lado, cx - lado / 2))), int(max(0, min(H - lado, cy - lado / 2)))
        lado = min(lado, W - x0, H - y0)
        recorte = img.crop((x0, y0, x0 + lado, y0 + lado)).resize((1024, 1024), Image.LANCZOS)
        # codifica o recorte NOS MESMOS fp16 (sem o "upcast" para fp32 do img2img, que dobrava a memoria e travava o PC)
        with torch.no_grad():
            px = _i2i.image_processor.preprocess(recorte).to("cuda", vae.dtype)
            base = vae.encode(px).latent_dist.sample(g) * vae.config.scaling_factor
        del px
        lat = _i2i(prompt="close-up portrait, detailed realistic symmetrical eyes, matching pupils, natural straight teeth, natural lips, natural skin texture, " + prompt[:200],
                   negative_prompt=NEGATIVO + ", deformed eyes, crossed eyes, asymmetrical eyes, different pupil sizes, deformed teeth, extra teeth, fused teeth, distorted mouth", image=base, strength=0.4 if h < H * 0.4 else 0.3,
                   num_inference_steps=10, guidance_scale=1.2, generator=g, output_type="latent").images
        with torch.no_grad():
            novo = vae.decode(lat.to(vae.dtype) / vae.config.scaling_factor).sample
        novo = pipe.image_processor.postprocess(novo.float(), output_type="pil")[0].resize((lado, lado), Image.LANCZOS)
        m = Image.new("L", (lado, lado), 0)
        ImageDraw.Draw(m).ellipse([lado * .12, lado * .08, lado * .88, lado * .92], fill=255)
        img.paste(novo, (x0, y0), m.filter(ImageFilter.GaussianBlur(lado // 12)))
        n += 1
        del lat, base
        torch.cuda.empty_cache()
    return img, n


def gerar(prompt, arquivo, proporcao="16:9", seed=None):
    return gerar_lote([{"prompt": prompt, "saida": arquivo, "proporcao": proporcao, "seed": seed}]) == 1


if __name__ == "__main__":
    a = sys.argv[1:]
    if a and a[0] == "_etapa":
        {"texto": etapa_texto, "imagem": etapa_imagem, "sdxl": etapa_sdxl}.get(a[1], lambda t: etapa_decodificar(t, a[3] if len(a) > 3 else "cuda"))(a[2])
    elif a and a[0] == "lote":
        print("prontas:", gerar_lote(json.load(open(a[1], encoding="utf-8"))))
    else:
        gerar(a[0], a[1], a[2] if len(a) > 2 else "16:9", a[3] if len(a) > 3 else None)
