#!/usr/bin/env python3
"""Validação end-to-end do modo dev (Chroma + cache JSON + Ollama)."""
from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.request

BASE = os.getenv("UPI_VALIDATE_BASE", "http://127.0.0.1:8000")
OLLAMA = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434")


def get(path: str, timeout: float = 10.0) -> tuple[int, dict]:
    req = urllib.request.Request(f"{BASE}{path}")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.status, json.loads(resp.read().decode())


def post(path: str, body: dict, timeout: float = 120.0) -> tuple[int, dict]:
    data = json.dumps(body).encode()
    req = urllib.request.Request(
        f"{BASE}{path}",
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.status, json.loads(resp.read().decode())


def check_ollama() -> None:
    req = urllib.request.Request(OLLAMA)
    with urllib.request.urlopen(req, timeout=5) as resp:
        if resp.status != 200:
            raise RuntimeError(f"Ollama status {resp.status}")


def main() -> int:
    errors: list[str] = []

    print("[1/6] Ollama...")
    try:
        check_ollama()
        print("  OK")
    except Exception as e:
        errors.append(f"Ollama: {e}")
        print(f"  FALHA: {e}")

    print("[2/6] GET /health...")
    try:
        code, data = get("/health")
        assert code == 200 and data.get("ok") is True
        print("  OK", data)
    except Exception as e:
        errors.append(f"/health: {e}")
        print(f"  FALHA: {e}")

    print("[3/6] GET /api/health (proxy front)...")
    try:
        code, data = get("/api/health")
        assert code == 200 and data.get("ok") is True
        print("  OK")
    except Exception as e:
        errors.append(f"/api/health: {e}")
        print(f"  FALHA: {e}")

    print("[4/6] POST /chat (LLM real, pode demorar)...")
    try:
        t0 = time.time()
        code, data = post("/chat", {"message": "oi"})
        elapsed = time.time() - t0
        assert code == 200
        assert data.get("response")
        assert data.get("emotion") in {
            "happy",
            "neutral",
            "sad",
            "excited",
            "thinking",
            "calm",
            "surprised",
            "confused",
        }
        print(f"  OK ({elapsed:.1f}s) emotion={data.get('emotion')}")
        print(f"  resposta: {str(data.get('response'))[:80]}...")
    except Exception as e:
        errors.append(f"/chat: {e}")
        print(f"  FALHA: {e}")

    print("[5/6] POST /chat cache hit (mesma pergunta)...")
    try:
        t0 = time.time()
        code, data = post("/chat", {"message": "oi"})
        elapsed = time.time() - t0
        assert code == 200 and data.get("response")
        print(f"  OK ({elapsed:.1f}s)")
    except Exception as e:
        errors.append(f"cache: {e}")
        print(f"  FALHA: {e}")

    print("[6/6] POST /ingest...")
    try:
        code, data = post(
            "/ingest",
            {
                "text": "Validação automática: NAPSI Bloco A Sala 12.",
                "metadata": {"source": "validate_dev_stack"},
            },
            timeout=60,
        )
        assert code == 200 and data.get("status") == "success"
        print("  OK")
    except Exception as e:
        errors.append(f"/ingest: {e}")
        print(f"  FALHA: {e}")

    if errors:
        print("\n=== VALIDAÇÃO FALHOU ===")
        for err in errors:
            print(f"  - {err}")
        return 1

    print("\n=== VALIDAÇÃO DEV OK ===")
    return 0


if __name__ == "__main__":
    sys.exit(main())
