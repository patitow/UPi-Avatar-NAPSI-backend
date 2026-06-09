# Sobe o stack de produção (Docker + Caddy :80) e, opcionalmente, DDNS Cloudflare.
param(
    [switch]$Build,
    [switch]$Ddns,
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

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    Write-Error "Docker não encontrado no PATH."
}

$files = @("-f", "docker-compose.yml", "-f", "docker-compose.prod.yml")
if (-not (Test-HostOllama)) {
    Write-Host "Ollama não encontrado no host — subindo container upi_ollama." -ForegroundColor Yellow
    Write-Host "  Depois: docker exec -it upi_ollama ollama pull llama3.2:3b" -ForegroundColor DarkYellow
    $files += "-f", "docker-compose.ollama.yml"
} else {
    Write-Host "Ollama detectado em http://127.0.0.1:11434 — API usará host.docker.internal." -ForegroundColor Green
}

$upArgs = @("compose") + $files + @("up")
if ($Build) { $upArgs += "--build" }
if ($Ddns) {
    $upArgs += "--profile", "ddns"
    Write-Host "DDNS Cloudflare ativo (profile ddns)." -ForegroundColor Cyan
    Write-Host "  Verifique CLOUDFLARE_API_TOKEN e DDNS_DOMAINS no .env" -ForegroundColor DarkYellow
} else {
    Write-Host "Sem DDNS — use -Ddns para atualizar api.upi.patitow.dev automaticamente." -ForegroundColor DarkYellow
}
$upArgs += $ComposeArgs

Write-Host ""
Write-Host "  Front (Vercel):  https://upi.patitow.dev" -ForegroundColor Green
Write-Host "  API (Caddy):     http://localhost (proxy → :8000 interno)" -ForegroundColor Green
Write-Host "  DDNS (opcional): docker compose logs -f cloudflare-ddns-upi" -ForegroundColor Green
Write-Host ""

& docker @upArgs
