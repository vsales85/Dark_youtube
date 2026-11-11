# Integração com o SupoClip (opcional)

O [SupoClip](https://github.com/FujiwaraChoki/supoclip) é um projeto de **outro autor**, licença **AGPL-3.0**
(cópia em `LICENSE-AGPL-3.0`). O Dark Studio funciona **sem ele** (vozes do Gemini e voz clonada já estão no app).
Use-o se quiser os recursos extras dele (clipes de vídeos do YouTube, biblioteca, em alta).

Esta pasta guarda **as modificações feitas para o Dark Studio** (também sob AGPL-3.0):
- `modificacoes.patch` — alterações em arquivos do SupoClip original (base: commit `4bc76f83b3427808464f117473ee61083c65cf1f`)
- `novos/` — arquivos novos (Studio "Vídeo do zero", narração, capas, em alta, voz clonada...)

## Montar igual ao PC original
```bash
git clone https://github.com/FujiwaraChoki/supoclip.git D:/SupoClip
cd D:/SupoClip
git checkout 4bc76f83b3427808464f117473ee61083c65cf1f
git apply <caminho>/integracoes/supoclip/modificacoes.patch
# copie o conteudo de integracoes/supoclip/novos/ por cima da pasta D:/SupoClip/
cp .env.example .env    # preencha as chaves (siga o README do SupoClip)
docker compose up -d --build
```
Depois, no `.env` do Dark Studio: `SUPOCLIP_ENV=D:\SupoClip\.env` e `SUPOCLIP_USER_ID=<id do seu usuario no SupoClip>`.
