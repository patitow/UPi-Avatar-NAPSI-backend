# Producao: Docker + Caddy/DDNS (padrao) OU Cloudflare Tunnel (-Tunnel).
param(
    [switch]$Build,
    [switch]$Ddns,
    [switch]$NoDdns,
    [switch]$NoOllama,
    [switch]$Tunnel,
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
    Write-Error "Docker nao encontrado no PATH."
}

$files = @("-f", "docker-compose.yml", "-f", "docker-compose.prod.yml")

if ($Tunnel) {
    $envFile = Join-Path $PSScriptRoot ".env"
    $hasToken = $false
    if (Test-Path $envFile) {
        foreach ($line in Get-Content $envFile) {
            if ($line -match '^\s*CLOUDFLARE_TUNNEL_TOKEN=(.+)$' -and $matches[1].Trim()) {
                $hasToken = $true
            }
        }
    }
    if (-not $hasToken) {
        Write-Error "CLOUDFLARE_TUNNEL_TOKEN em falta no .env. Ver docker-compose.tunnel.yml"
    }
    $files += "-f", "docker-compose.tunnel.yml"
    Write-Host "Modo Cloudflare Tunnel (sem Caddy/DDNS/port forward)." -ForegroundColor Cyan
} else {
    $certPem = Join-Path $PSScriptRoot "certs\origin.pem"
    $certKey = Join-Path $PSScriptRoot "certs\origin-key.pem"
    if (-not ((Test-Path $certPem) -and (Test-Path $certKey))) {
        Write-Error "Certificados Cloudflare em falta. Ver certs/README.md ou use -Tunnel"
    }
}

$useOpenAiEmbeddings = (-not $NoOllama) -and (Test-OpenAiEmbeddingsConfigured)

if ($useOpenAiEmbeddings) {
    Write-Host "LLM + embeddings via OpenAI - Ollama nao necessario." -ForegroundColor Green
} elseif ($NoOllama) {
    Write-Host "Ollama desligado (-NoOllama)." -ForegroundColor Yellow
} elseif (Test-HostOllama) {
    Write-Host "Ollama detectado em http://127.0.0.1:11434" -ForegroundColor Green
} else {
    Write-Host "Ollama nao encontrado - subindo container upi_ollama." -ForegroundColor Yellow
    $files += "-f", "docker-compose.ollama.yml"
}

$useDdns = (-not $Tunnel) -and ($Ddns -or (-not $NoDdns))

$upArgs = @("compose") + $files
if ($useDdns) {
    $upArgs += "--profile", "ddns"
    Write-Host "DDNS Cloudflare ativo." -ForegroundColor Cyan
}
if ($Tunnel) {
    $upArgs += "--profile", "tunnel"
} else {
    $upArgs += "--profile", "prod"
}
$upArgs += "up"
if ($Build) { $upArgs += "--build" }
$upArgs += $ComposeArgs

Write-Host ""
Write-Host "  API: https://api.upi.patitow.dev/health" -ForegroundColor Green
Write-Host ""

& docker @upArgs
