# Deploy do backend UPi (casa + Cloudflare, HTTPS end-to-end)

Guia completo: [`../DEPLOY.md`](../DEPLOY.md).

## HTTPS end-to-end

```
Browser ──HTTPS──► Cloudflare ──HTTPS──► Caddy (:443) ──► API (:8000)
```

Modo Cloudflare: **Full (strict)** — certificado **Origin** no Caddy.

## Setup (uma vez)

### 1. Origin Certificate (Cloudflare)

**Onde:** zona `patitow.dev` → **SSL/TLS** → **Origin Server** → **Create Certificate**

- Hostname: `api.upi.patitow.dev`
- Guardar em:
  - `certs/origin.pem`
  - `certs/origin-key.pem`

Detalhes: [`certs/README.md`](certs/README.md)

### 2. SSL mode (Cloudflare)

**Onde:** **SSL/TLS** → **Overview** → **Full (strict)**

### 3. Router

Port forward **TCP 443** → IP LAN deste PC (80 opcional, redirect HTTP→HTTPS no Caddy).

### 4. `.env`

```env
UPI_DEV_MODE=0
OPENAI_API_KEY=sk-...
CORS_ORIGINS=https://upi.patitow.dev,http://localhost:5173
CLOUDFLARE_API_TOKEN=...
DDNS_DOMAINS=api.upi.patitow.dev
```

### 5. Subir

```powershell
.\compose-prod.ps1 -Ddns
```

## Verificar

```powershell
curl https://api.upi.patitow.dev/health
```

Esperado: `{"status":"healthy","ok":true}`
