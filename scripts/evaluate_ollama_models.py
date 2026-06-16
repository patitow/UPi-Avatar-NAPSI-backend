#!/usr/bin/env python3
"""Compara modelos Ollama locais nas mesmas perguntas NAPSI (via API)."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import List

BASE = "http://127.0.0.1:8000"
BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

CASES = [
    {
        "id": "onde_fica",
        "message": "Onde fica o NAPSI?",
        "required": [r"bloco", r"sala"],
        "forbidden": [r"tempo\s+extraordin", r"transtorno\s+do\s+tempo"],
    },
    {
        "id": "agendar",
        "message": "Como agendar um atendimento?",
        "required": [r"agendar|e-?mail|formul[aá]rio", r"napsi"],
        "forbidden": [],
    },
    {
        "id": "servicos",
        "message": "Quais serviços o NAPSI oferece?",
        "required": [r"psicoped|psicol[oó]g|acolhimento|servi[cç]o"],
        "forbidden": [r"tempo\s+extraordin"],
    },
    {
        "id": "tea",
        "message": "O NAPSI apoia alunos com TEA?",
        "required": [r"tea|autis|espectro"],
        "forbidden": [r"tempo\s+extraordin", r"transtorno\s+do\s+tempo"],
    },
]


def case_passes(case: dict, text: str) -> bool:
    import re

    lower = text.lower()
    if not all(re.search(p, lower) for p in case["required"]):
        return False
    for bad in case.get("forbidden", []):
        if re.search(bad, lower):
            return False
    return True

# Modelos a comparar (ajuste via env EVAL_MODELS=csv)
DEFAULT_MODELS = [
    "llama3.2:3b",
    "llama3.1:8b",
    "qwen3.5:9b",
    "mistral:latest",
]


@dataclass
class CaseResult:
    case_id: str
    ok: bool
    latency_s: float
    response: str
    emotion: str


def wait_health(timeout: float = 90.0) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(f"{BASE}/health", timeout=3) as r:
                if r.status == 200:
                    return
        except Exception:
            pass
        time.sleep(2)
    raise TimeoutError("API não subiu a tempo")


def stop_server(proc: subprocess.Popen | None) -> None:
    if proc and proc.poll() is None:
        proc.terminate()
        try:
            proc.wait(timeout=15)
        except subprocess.TimeoutExpired:
            proc.kill()


def start_server(model: str) -> subprocess.Popen:
    env = os.environ.copy()
    env["UPI_DEV_MODE"] = "1"
    env["TTS_PROVIDER"] = "none"
    env["OLLAMA_MODEL"] = model
    env["DEV_CACHE_PATH"] = os.path.join(
        BACKEND_DIR, "data", f"eval_cache_{model.replace(':', '_')}.json"
    )
    env["CHROMA_PERSIST_DIR"] = os.path.join(
        BACKEND_DIR, "data", f"chroma_eval_{model.replace(':', '_')}"
    )
    return subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8000"],
        cwd=BACKEND_DIR,
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
    )


def chat(message: str, timeout: float = 120.0) -> dict:
    data = json.dumps({"message": message}).encode()
    req = urllib.request.Request(
        f"{BASE}/chat",
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode())


def eval_model(model: str) -> dict:
    proc = start_server(model)
    results: List[CaseResult] = []
    try:
        wait_health()
        for case in CASES:
            t0 = time.time()
            try:
                out = chat(case["message"])
                text = str(out.get("response", ""))
                emo = str(out.get("emotion", ""))
                lat = time.time() - t0
                ok = case_passes(case, text)
                results.append(
                    CaseResult(case["id"], ok, lat, text[:300], emo)
                )
            except Exception as e:
                results.append(
                    CaseResult(case["id"], False, time.time() - t0, str(e)[:200], "")
                )
    finally:
        stop_server(proc)

    passed = sum(1 for r in results if r.ok)
    avg_lat = sum(r.latency_s for r in results) / max(len(results), 1)
    return {
        "model": model,
        "passed": passed,
        "total": len(results),
        "avg_latency_s": round(avg_lat, 1),
        "cases": [
            {
                "id": r.case_id,
                "ok": r.ok,
                "latency_s": round(r.latency_s, 1),
                "emotion": r.emotion,
                "response": r.response,
            }
            for r in results
        ],
    }


def main() -> int:
    raw = os.getenv("EVAL_MODELS", "")
    models = [m.strip() for m in raw.split(",") if m.strip()] or DEFAULT_MODELS

    print("Modelos:", ", ".join(models))
    report = []
    for model in models:
        print(f"\n=== {model} ===")
        row = eval_model(model)
        report.append(row)
        print(f"  {row['passed']}/{row['total']} casos OK · média {row['avg_latency_s']}s")
        for c in row["cases"]:
            mark = "OK" if c["ok"] else "FALHA"
            print(f"  [{mark}] {c['id']} ({c['latency_s']}s): {c['response'][:80]}...")

    out_path = os.path.join(BACKEND_DIR, "data", "model_eval_report.json")
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print(f"\nRelatório: {out_path}")
    failed = sum(1 for row in report if row["passed"] < row["total"])
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
