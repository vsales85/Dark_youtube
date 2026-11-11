# Voz clonada do VTube: Chatterbox Multilingual (MIT) só no processador.
FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg libsndfile1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
# PyTorch só CPU (bem menor que a versão com CUDA).
RUN pip install --no-cache-dir torch torchaudio --index-url https://download.pytorch.org/whl/cpu \
    && pip install --no-cache-dir chatterbox-tts fastapi "uvicorn[standard]"

# Números por extenso em português antes de narrar.
RUN pip install --no-cache-dir num2words

COPY servidor.py .
ENV HF_HOME=/modelos
VOLUME ["/modelos", "/vozes"]
EXPOSE 3900
CMD ["uvicorn", "servidor:app", "--host", "0.0.0.0", "--port", "3900"]
