# Deploy do backend UPi (casa + Cloudflare)

Stack de produção: Postgres, Redis, API FastAPI, Caddy (`:80`) e, opcionalmente, DDNS Cloudflare.

Guia completo (front Vercel + DNS): [`../DEPLOY.md`](../DEPLOY.md).

## Comandos

```powershell
# Produção com DDNS (recomendado)
.\compose-prod.ps1 -Ddns

# Rebuild da imagem da API
.\compose-prod.ps1 -Build -Ddns

# Só stack local (sem DDNS) — útil para testar Caddy
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d
```

## Variáveis `.env` (produção)

```env
UPI_DEV_MODE=0
CORS_ORIGINS=https://upi.patitow.dev,http://localhost:5173
CLOUDFLARE_API_TOKEN=...
DDNS_DOMAINS=api.upi.patitow.dev
OPENAI_API_KEY=...
OLLAMA_MODEL=llama3.2:3b
```

## Rede

- Router: **TCP 80** → este PC
- Cloudflare: registo A `api.upi.patitow.dev`, proxy ligado, SSL **Flexible**
- DDNS: mesmo padrão do projeto Minecraft (`favonia/cloudflare-ddns`)

## Arquivos

| Arquivo | Função |
|---------|--------|
| `docker-compose.prod.yml` | Caddy + DDNS; API só na rede interna Docker |
| `Caddyfile` | `:80` → `api:8000` |
| `compose-prod.ps1` | Sobe stack + profile `ddns` |
