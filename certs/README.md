# Certificados Cloudflare Origin (NÃO commitar)

Gera na Cloudflare e guarda aqui com estes nomes exatos:

| Ficheiro | Conteúdo |
|----------|----------|
| `origin.pem` | Origin Certificate (bloco PEM completo) |
| `origin-key.pem` | Private Key (bloco PEM completo) |

## Passo a passo

1. [dash.cloudflare.com](https://dash.cloudflare.com) → zona **patitow.dev**
2. **SSL/TLS** → **Origin Server** → **Create Certificate**
3. Hostnames: `api.upi.patitow.dev` (ou `*.patitow.dev` + `patitow.dev`)
4. Validade: 15 years (padrão)
5. **Create** → copia **Origin Certificate** para `origin.pem`
6. Copia **Private Key** para `origin-key.pem`
7. **SSL/TLS** → **Overview** → modo **Full (strict)**
8. Router: port forward **TCP 443** → IP LAN deste PC (pode manter 80 para redirect)

## Verificar

```powershell
# Ficheiros existem?
Test-Path certs/origin.pem, certs/origin-key.pem

# Depois de subir o stack
curl https://api.upi.patitow.dev/health
```

Os ficheiros `.pem` estão no `.gitignore` — nunca vão para o Git.
