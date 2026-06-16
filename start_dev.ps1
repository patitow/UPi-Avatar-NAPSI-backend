# UPi backend - desenvolvimento sem Docker (Chroma + cache JSON + Ollama)
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

$env:UPI_DEV_MODE = "1"
$env:OLLAMA_BASE_URL = "http://localhost:11434"

if (Test-Path ".env") {
    Get-Content ".env" | ForEach-Object {
        if ($_ -match '^\s*OLLAMA_MODEL=(.+)$') {
            $env:OLLAMA_MODEL = $matches[1].Trim().Trim('"').Trim("'")
        }
    }
}
if (-not $env:OLLAMA_MODEL) {
    $env:OLLAMA_MODEL = "llama3.2:3b"
}

Write-Host "UPi - modo DEV (sem Postgres/Redis)" -ForegroundColor Cyan

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

$model = $env:OLLAMA_MODEL
if (-not (ollama list 2>$null | Select-String $model)) {
    Write-Host "Baixando $model (primeira vez)..." -ForegroundColor Yellow
    ollama pull $model
}

function Test-PythonImport {
    param([string]$Module)
    $prev = $ErrorActionPreference
    $ErrorActionPreference = "SilentlyContinue"
    python -c "import $Module" 2>$null | Out-Null
    $ok = $LASTEXITCODE -eq 0
    $ErrorActionPreference = $prev
    return $ok
}

if (-not (Test-PythonImport "fastapi")) {
    Write-Host "Instalando dependencias (requirements-dev.txt)..." -ForegroundColor Yellow
    pip install -r requirements-dev.txt
} elseif (-not (Test-PythonImport "chromadb")) {
    pip install chromadb
}

New-Item -ItemType Directory -Force -Path data, data/chroma_db | Out-Null

Write-Host ""
Write-Host "  Modelo:  $env:OLLAMA_MODEL (LLM + embeddings)" -ForegroundColor Green
Write-Host "  Vector:  Chroma (data/chroma_db)" -ForegroundColor Green
Write-Host "  Dica:    ao trocar de modelo, apague data/chroma_db e data/dev_semantic_cache.json" -ForegroundColor DarkYellow
Write-Host "  Cache:   data/dev_semantic_cache.json" -ForegroundColor Green
Write-Host "  API:     http://localhost:8000" -ForegroundColor Green
Write-Host ""

python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
