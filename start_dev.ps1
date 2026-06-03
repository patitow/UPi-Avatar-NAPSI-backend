# UPi backend — desenvolvimento sem Docker (Chroma + cache JSON + Ollama)
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

$env:UPI_DEV_MODE = "1"
$env:OLLAMA_BASE_URL = "http://localhost:11434"
$env:OLLAMA_MODEL = "llama3.2:3b"

Write-Host "UPi — modo DEV (sem Postgres/Redis)" -ForegroundColor Cyan

if (-not (Get-Command ollama -ErrorAction SilentlyContinue)) {
    Write-Error "Instale Ollama: https://ollama.com"
}

try {
    Invoke-WebRequest -Uri "http://127.0.0.1:11434/" -UseBasicParsing -TimeoutSec 2 | Out-Null
} catch {
    Write-Host "Iniciando ollama serve..." -ForegroundColor Yellow
    Start-Process ollama -ArgumentList "serve" -WindowStyle Hidden
    Start-Sleep -Seconds 3
}

$model = "llama3.2:3b"
if (-not (ollama list 2>$null | Select-String $model)) {
    Write-Host "Baixando $model (primeira vez)..." -ForegroundColor Yellow
    ollama pull $model
}

if (-not (python -c "import fastapi" 2>$null)) {
    pip install -r requirements-dev.txt
} elseif (-not (python -c "import chromadb" 2>$null)) {
    pip install chromadb
}

New-Item -ItemType Directory -Force -Path data, data/chroma_db | Out-Null

Write-Host ""
Write-Host "  Vector:  Chroma (data/chroma_db)" -ForegroundColor Green
Write-Host "  Cache:   data/dev_semantic_cache.json" -ForegroundColor Green
Write-Host "  API:     http://localhost:8000" -ForegroundColor Green
Write-Host ""

python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
