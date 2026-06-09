# Produção em casa: stack UPi em container + Caddy HTTPS (:443) + DDNS Cloudflare.
# Equivalente ao mine.patitow.dev — ver server.json e certs/README.md.
param(
    [switch]$Build,
    [switch]$Ddns,
    [switch]$NoDdns,
    [switch]$NoOllama,
    [string[]]$ComposeArgs = @("-d")
)

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

function Test-HostOllama {
    try {
        Invoke-WebRequest -Uri "http://127.0.0.1:11434/" -UseBasicParsing -TimeoutSec 2 | Out-Null
        return $true
    } catch {
        return $false
    }
}

function Test-OpenAiEmbeddingsConfigured {
    $envFile = Join-Path $PSScriptRoot ".env"
    if (-not (Test-Path $envFile)) { return $false }

    $provider = "auto"
    $hasKey = $false
    foreach ($line in Get-Content $envFile) {
        if ($line -match '^\s*#') { continue }
        if ($line -match '^\s*EMBEDDINGS_PROVIDER=(.+)$') {
            $provider = $matches[1].Trim().Trim('"').Trim("'").ToLower()
        }
        if ($line -match '^\s*OPENAI_API_KEY=(.+)$') {
            $val = $matches[1].Trim().Trim('"').Trim("'")
            if ($val) { $hasKey = $true }
        }
    }

    if ($provider -eq "ollama") { return $false }
    if ($provider -eq "openai") { return $hasKey }
    return $hasKey
}

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    Write-Error "Docker não encontrado no PATH."
}

$certPem = Join-Path $PSScriptRoot "certs\origin.pem"
$certKey = Join-Path $PSScriptRoot "certs\origin-key.pem"
if (-not ((Test-Path $certPem) -and (Test-Path $certKey))) {
    Write-Error @"
Certificados Cloudflare em falta.

Cria certs/origin.pem e certs/origin-key.pem (Origin Certificate).
Instruções: certs/README.md

Cloudflare → SSL/TLS → Origin Server → Create Certificate
Depois: SSL/TLS → Overview → Full (strict)
"@
}

$files = @("-f", "docker-compose.yml", "-f", "docker-compose.prod.yml")
$useOpenAiEmbeddings = (-not $NoOllama) -and (Test-OpenAiEmbeddingsConfigured)

if ($useOpenAiEmbeddings) {
    Write-Host "LLM + embeddings via OpenAI — Ollama não necessário." -ForegroundColor Green
} elseif ($NoOllama) {
    Write-Host "Ollama desligado (-NoOllama)." -ForegroundColor Yellow
} elseif (Test-HostOllama) {
    Write-Host "Ollama detectado em http://127.0.0.1:11434 — API usará host.docker.internal." -ForegroundColor Green
} else {
    Write-Host "Ollama não encontrado no host — subindo container upi_ollama." -ForegroundColor Yellow
    Write-Host "  Depois: docker exec -it upi_ollama ollama pull llama3.2:3b" -ForegroundColor DarkYellow
    $files += "-f", "docker-compose.ollama.yml"
}

$upArgs = @("compose") + $files + @("--profile", "prod", "up")
if ($Build) { $upArgs += "--build" }

$useDdns = $Ddns -or (-not $NoDdns)
if ($useDdns) {
    $upArgs += "--profile", "ddns"
    Write-Host "DDNS Cloudflare ativo (profile ddns)." -ForegroundColor Cyan
    Write-Host "  Verifique CLOUDFLARE_API_TOKEN e DDNS_DOMAINS no .env" -ForegroundColor DarkYellow
} else {
    Write-Host "Sem DDNS (-NoDdns). DNS no Cloudflare não será atualizado." -ForegroundColor DarkYellow
}
$upArgs += $ComposeArgs

Write-Host ""
Write-Host "  Domínio API:     https://api.upi.patitow.dev" -ForegroundColor Green
Write-Host "  Front (Vercel):  https://upi.patitow.dev" -ForegroundColor Green
Write-Host "  Teste local:     curl -k https://localhost/health  (ou via domínio)" -ForegroundColor Green
Write-Host "  Logs DDNS:       docker compose -f docker-compose.yml -f docker-compose.prod.yml logs -f cloudflare-ddns-upi" -ForegroundColor Green
Write-Host ""

& docker @upArgs
