#!/bin/bash
# deploy.sh - Script de Deploy Automatizado para a VPS

# Garante que o script para se houver algum erro
set -e

echo "=========================================="
echo "          INICIANDO DEPLOY UPi"
echo "=========================================="

# 1. Puxa a versão mais recente do código
echo "-> Puxando atualizações do Git (Force Sync)..."
git fetch --all
git reset --hard origin/main
git clean -fd
# 2. Sobe/Atualiza os containers da stack de produção (API, DB, Redis, Caddy)
echo "-> Construindo e iniciando os containers..."
docker compose -f docker-compose.yml -f docker-compose.prod.yml --profile prod up -d --build

echo "=========================================="
echo "      DEPLOY FINALIZADO COM SUCESSO!"
echo "=========================================="
