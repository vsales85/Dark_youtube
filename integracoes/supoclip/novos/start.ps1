# SupoClip - Quick Start Script for Windows (PowerShell)
$ErrorActionPreference = "Stop"

Write-Host "============================================" -ForegroundColor Cyan
Write-Host "  SupoClip - AI Video Clipping Tool" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""

$envPath = Join-Path $PSScriptRoot ".env"

if (-not (Test-Path $envPath)) {
    Write-Host "Error: Arquivo .env nao encontrado!" -ForegroundColor Red
    Write-Host "Crie o arquivo .env copiando de .env.example e configure suas chaves de API."
    exit 1
}

# Carregar variaveis do .env
Get-Content $envPath | Where-Object { $_ -match '^([^#=]+)=(.*)$' } | ForEach-Object {
    $name = $matches[1].Trim()
    $value = $matches[2].Trim()
    [System.Environment]::SetEnvironmentVariable($name, $value, "Process")
}

$frontendPort = if ($env:FRONTEND_PORT) { $env:FRONTEND_PORT } else { "3107" }
$frontendUrl = "http://localhost:$frontendPort"

# Validacoes de configuracao
if (-not $env:ASSEMBLY_AI_API_KEY -and $env:TRANSCRIPTION_PROVIDER -ne "whisper" -and $env:TRANSCRIPTION_PROVIDER -ne "youtube_captions") {
    Write-Host "[AVISO] ASSEMBLY_AI_API_KEY nao esta configurada no .env!" -ForegroundColor Yellow
    Write-Host "        (Se preferir usar transcricao local gratuita sem chave, defina TRANSCRIPTION_PROVIDER=whisper no .env)" -ForegroundColor Yellow
    Write-Host ""
}

if (-not $env:OPENAI_API_KEY -and -not $env:GOOGLE_API_KEY -and -not $env:ANTHROPIC_API_KEY -and -not $env:OPENROUTER_API_KEY -and ($env:LLM -notmatch '^ollama:')) {
    Write-Host "[AVISO] Nenhuma chave de IA foi definida no .env (GOOGLE_API_KEY, OPENAI_API_KEY, etc.) nem LLM=ollama:!" -ForegroundColor Yellow
    Write-Host "        Configure uma chave no .env para deteccao dos melhores cortes." -ForegroundColor Yellow
    Write-Host ""
}

# Verificar se Docker esta rodando
Write-Host "Verificando se o Docker esta em execucao..." -ForegroundColor Gray
$dockerRunning = $false
try {
    $null = docker info 2>&1
    if ($LASTEXITCODE -eq 0) {
        $dockerRunning = $true
    }
} catch {
    $dockerRunning = $false
}

if (-not $dockerRunning) {
    Write-Host "[ERRO] O Docker Desktop nao esta rodando!" -ForegroundColor Red
    Write-Host "Por favor, abra o aplicativo Docker Desktop no Windows e tente novamente." -ForegroundColor Yellow
    exit 1
}

# Determinar comando docker compose
$composeCmd = "docker compose"
try {
    $null = docker compose version 2>&1
    if ($LASTEXITCODE -ne 0) {
        $composeCmd = "docker-compose"
    }
} catch {
    $composeCmd = "docker-compose"
}

Write-Host "Iniciando SupoClip com $composeCmd..." -ForegroundColor Green
Write-Host "Construindo imagens e iniciando conteineres (pode demorar alguns minutos na primeira vez)..." -ForegroundColor Gray
Write-Host ""

Set-Location $PSScriptRoot

if ($composeCmd -eq "docker compose") {
    docker compose up -d --build
} else {
    docker-compose up -d --build
}

Write-Host ""
Write-Host "SupoClip iniciado com sucesso!" -ForegroundColor Green
Write-Host ""
Write-Host "Acesse nos links:" -ForegroundColor Cyan
Write-Host "  - Frontend:  $frontendUrl"
Write-Host "  - Backend:   http://localhost:8000"
Write-Host "  - API Docs:  http://localhost:8000/docs"
Write-Host ""
Write-Host "Comandos uteis:" -ForegroundColor Gray
Write-Host "  - Ver logs:     $composeCmd logs -f"
Write-Host "  - Parar tudo:   $composeCmd down"
Write-Host "============================================" -ForegroundColor Cyan
