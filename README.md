# Dark Studio

Painel local (Windows) que **cria vídeos para o YouTube com IA** e deixa você só **aprovar e agendar**:

- 🗺️ **Mapa animado** — Shorts e vídeos de história com mapa-múndi, bandeiras, rotas, tropas e **mais de 110 bonequinhos animados** (desenhados por código, sem placa de vídeo).
- 🎬 **Vídeos cinematográficos** — roteiro + narração + imagens geradas no PC (precisa de placa de vídeo).
- 📤 **Publicação no YouTube** — título, descrição, tags, miniatura, “feito com IA”, agendamento.

O roteiro é escrito pelo **Gemini (grátis)**; voz, desenho e montagem rodam **no seu PC**.

---

## Requisitos

| | Mínimo | Para imagens geradas no PC |
|---|---|---|
| Sistema | Windows 10/11 | Windows 10/11 |
| Python | **3.12** ([download](https://www.python.org/downloads/) — marque *Add python.exe to PATH*) | 3.12 |
| Memória | 8 GB | 16–32 GB |
| Placa de vídeo | não precisa (mapa animado roda no processador) | NVIDIA ou AMD com 12–16 GB |
| Disco | ~2 GB | +10 GB |
| Internet | sim (roteiro, voz e 1º download dos mapas) | sim |

## Instalação (passo a passo)

1. **Baixe o projeto**
   - com Git: `git clone https://github.com/vsales85/Dark_youtube.git`
   - ou no GitHub: **Code → Download ZIP** e extraia numa pasta (ex.: `C:\DarkStudio`).
2. **Dê dois cliques em `INSTALAR.bat`**. Ele:
   - cria um ambiente Python isolado (`.venv`);
   - pergunta a sua placa de vídeo (NVIDIA / AMD / nenhuma) e instala o PyTorch certo;
   - instala as bibliotecas (`requirements.txt`);
   - baixa os **mapas, fronteiras e fontes livres** (~400 MB, só na primeira vez);
   - cria o arquivo `.env`.
3. **Crie sua chave grátis do Gemini** em <https://aistudio.google.com/apikey> e cole no `.env`:
   ```
   GEMINI_API_KEY=sua_chave_aqui
   ```
4. **Dê dois cliques em `ABRIR_PAINEL.bat`** → o painel abre em <http://localhost:8765>.
5. (Opcional) **Imagens geradas no PC**: `.venv\Scripts\python baixar_dados.py --imagens` (~7 GB).

## Roteiro sem travar (opcional, recomendado)

O roteiro é escrito pelo **Gemini**. Se ele estiver sobrecarregado ou a cota do dia acabar, o app usa
**automaticamente** um modelo no próprio PC com o [Ollama](https://ollama.com) (grátis, sem limite, sem internet):

1. Instale o Ollama.
2. No terminal: `ollama pull qwen2.5:14b` (~9 GB; com pouca memória de vídeo use `qwen2.5:7b` e coloque `OLLAMA_MODELO=qwen2.5:7b` no `.env`).

O modelo é descarregado da placa logo após escrever, para não disputar com o gerador de imagens.

## Publicar no YouTube (opcional)

1. No [Google Cloud Console](https://console.cloud.google.com/), crie um projeto, ative a **YouTube Data API v3** e crie uma credencial **OAuth → App para computador**.
2. Baixe o JSON e salve na pasta do app como **`client_secret.json`**.
3. Rode uma vez `.venv\Scripts\python youtube.py` e autorize no navegador (gera `token.json`).
4. Para miniaturas personalizadas, verifique o canal em <https://www.youtube.com/verify>.

## Vozes (tudo dentro do app)

| Voz | Como funciona | Precisa de |
|---|---|---|
| **Edge TTS** (Antonio, Francisca, Thalita…) | grátis, pela internet | nada |
| **Gemini** (Charon, Kore, Puck… 30 vozes, as mais naturais) | `voz.py` chama o Gemini TTS com a **sua** `GEMINI_API_KEY` | a mesma chave do roteiro |
| **Voz clonada** (sua voz) | Chatterbox (MIT) rodando **no seu PC**, pasta `voz_clone/` | Docker Desktop |

**Voz clonada — passo a passo**
1. Instale o [Docker Desktop](https://www.docker.com/products/docker-desktop/).
2. Grave 10–30 s da sua voz (sem música/ruído) e salve em `vozes/minha-voz.wav`, com `vozes/minha-voz.json` = `{"nome": "Minha Voz", "genero": "Male"}`.
3. No terminal: `cd voz_clone` e `docker compose up -d --build` (1ª vez demora; baixa o modelo ~2 GB).
4. A voz aparece no painel em **Voz do narrador → Minhas vozes**.

Se uma voz de IA falhar (sem cota/serviço desligado), o app usa o Edge automaticamente — o vídeo nunca trava.
Só clone vozes suas ou de quem autorizou.

## Estrutura

| Arquivo | O que faz |
|---|---|
| `painel.py` / `painel.html` | painel web (fila, aprovação, agenda, gastos) |
| `gerar_video.py` | roteiro → narração → imagens → montagem |
| `mapa_animado.py` | motor dos vídeos de mapa (Skia + FFmpeg) |
| `avatares.py` / `objetos.py` | bonequinhos, veículos, construções, animais e astros |
| `imagem_local.py` | geração de imagens no PC (RealVisXL, opcional) |
| `voz.py` | vozes do Gemini (TTS) e voz clonada |
| `voz_clone/` | serviço local de clonagem de voz (Docker) |
| `youtube.py` / `seo.py` | publicação e textos de SEO |
| `config.py` | caminhos (troque pelo `.env`, ex.: `DARK_MODELOS=D:\modelos`) |
| `baixar_dados.py` | baixa mapas/fontes/modelos livres |

## Segurança

- **Nunca** envie `.env`, `token.json` ou `client_secret.json` para o GitHub (já estão no `.gitignore`).
- Vídeos, projetos e modelos ficam fora do repositório.

## Créditos e licenças de terceiros

- Mapas: [Natural Earth](https://www.naturalearthdata.com/) — domínio público.
- Bandeiras e retratos: [Wikimedia Commons](https://commons.wikimedia.org/) (símbolos oficiais / domínio público).
- Ícones: [Twemoji](https://github.com/jdecked/twemoji) — CC-BY 4.0 (crédito na descrição dos vídeos).
- Fontes: Google Fonts — SIL Open Font License.
- Detector de rosto: [OpenCV Zoo YuNet](https://github.com/opencv/opencv_zoo).
- Modelo de imagens: [RealVisXL V5 Lightning](https://huggingface.co/SG161222/RealVisXL_V5.0_Lightning) — confira a licença do autor.
