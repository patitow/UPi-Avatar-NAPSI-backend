"""Benchmark rápido de latência do endpoint /chat."""
import json
import sys
import time
import urllib.request

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8000"


def post_chat(message: str) -> dict:
    url = f"{BASE.rstrip('/')}/chat"
    data = json.dumps({"message": message}).encode()
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    t0 = time.perf_counter()
    with urllib.request.urlopen(req, timeout=120) as resp:
        body = resp.read()
    elapsed = time.perf_counter() - t0
    payload = json.loads(body)
    payload["_elapsed_s"] = round(elapsed, 3)
    return payload


if __name__ == "__main__":
    for msg in ["oi", "onde fica o NAPSI?", "oi"]:
        try:
            out = post_chat(msg)
            audio = out.get("audio") or ""
            print(
                f"{out['_elapsed_s']:>6.3f}s | {msg!r} | "
                f"audio={len(audio)} chars | {str(out.get('response', ''))[:70]}"
            )
        except Exception as exc:
            print(f"ERR | {msg!r} | {exc}")
