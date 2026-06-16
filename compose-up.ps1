# Sobe o stack Docker: usa Ollama da máquina se já estiver em :11434; senão sobe o container upi_ollama.
param(
    [switch]$Build,
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

$upArgs = @("compose", "up")
if ($Build) { $upArgs += "--build" }
$upArgs += $ComposeArgs

if (Test-HostOllama) {
    Write-Host "Ollama detectado em http://127.0.0.1:11434 — API usará host.docker.internal (sem container ollama)." -ForegroundColor Green
    & docker @upArgs
} else {
    Write-Host "Ollama não encontrado no host — subindo container upi_ollama." -ForegroundColor Yellow
    Write-Host "  Depois: docker exec -it upi_ollama ollama pull llama3.2:3b" -ForegroundColor DarkYellow
    $files = @("-f", "docker-compose.yml", "-f", "docker-compose.ollama.yml")
    & docker @($files + $upArgs[1..($upArgs.Length - 1)])
}
