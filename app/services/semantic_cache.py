"""Cache semântico: Redis (produção/Docker) ou memória + JSON (desenvolvimento)."""
from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any, List, Optional, Protocol

from app.services.intent import classify_intent


def _cosine_distance(a: List[float], b: List[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(x * x for x in b))
    if na == 0 or nb == 0:
        return 1.0
    return 1.0 - dot / (na * nb)


class SemanticCacheBackend(Protocol):
    def lookup(self, user_input: str) -> Optional[str]:
        ...

    def store(self, user_input: str, response_text: str) -> None:
        ...


class DevSemanticCache:
    """RAM + arquivo JSON — sem Redis."""

    def __init__(
        self,
        embeddings: Any,
        cache_path: str,
        distance_threshold: float,
    ):
        self.embeddings = embeddings
        self.threshold = distance_threshold
        self.path = Path(cache_path)
        self.entries: list[dict] = []
        self._load()

    def _load(self) -> None:
        if not self.path.exists():
            return
        try:
            self.entries = json.loads(self.path.read_text(encoding="utf-8"))
            for entry in self.entries:
                if not entry.get("intent") and entry.get("prompt"):
                    entry["intent"] = classify_intent(entry["prompt"])
        except Exception as e:
            print(f"[AVISO] Cache dev: falha ao ler {self.path}: {e}", flush=True)
            self.entries = []

    def _save(self) -> None:
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(
                json.dumps(self.entries, ensure_ascii=False),
                encoding="utf-8",
            )
        except Exception as e:
            print(f"[AVISO] Cache dev: falha ao gravar {self.path}: {e}", flush=True)

    def lookup(self, user_input: str) -> Optional[str]:
        if not self.embeddings or not self.entries:
            return None
        try:
            query_intent = classify_intent(user_input)
            query_vec = self.embeddings.embed_query(user_input)
            best_dist = 2.0
            best_response: Optional[str] = None
            for entry in self.entries:
                if entry.get("intent") and entry["intent"] != query_intent:
                    continue
                dist = _cosine_distance(query_vec, entry["vector"])
                if dist < best_dist:
                    best_dist = dist
                    best_response = entry.get("response")
            if best_response is not None and best_dist < self.threshold:
                print(
                    f"[CACHE HIT dev] intent={query_intent} dist={best_dist:.4f}",
                    flush=True,
                )
                return best_response
        except Exception as e:
            print(f"[AVISO] Cache dev lookup: {e}", flush=True)
        return None

    def store(self, user_input: str, response_text: str) -> None:
        if not self.embeddings:
            return
        try:
            vector = self.embeddings.embed_query(user_input)
            self.entries.append(
                {
                    "prompt": user_input,
                    "response": response_text,
                    "vector": vector,
                    "intent": classify_intent(user_input),
                }
            )
            self._save()
            print(f"[CACHE STORE dev] {user_input[:40]!r}...", flush=True)
        except Exception as e:
            print(f"[AVISO] Cache dev store: {e}", flush=True)


class RedisSemanticCache:
    """RedisVL — uso com Docker / produção."""

    def __init__(
        self,
        embeddings: Any,
        redis_url: str,
        distance_threshold: float,
    ):
        self.embeddings = embeddings
        self.redis_url = redis_url
        self.threshold = distance_threshold

    def _index(self):
        from redisvl.index import SearchIndex

        probe = self.embeddings.embed_query("cache_probe")
        schema = {
            "index": {"name": "upi_cache", "prefix": "cache"},
            "fields": [
                {"name": "prompt", "type": "text"},
                {"name": "response", "type": "text"},
                {"name": "intent", "type": "tag"},
                {
                    "name": "prompt_vector",
                    "type": "vector",
                    "attrs": {
                        "dims": len(probe),
                        "distance_metric": "cosine",
                        "algorithm": "flat",
                        "datatype": "float32",
                    },
                },
            ],
        }
        idx = SearchIndex.from_dict(schema, redis_url=self.redis_url)
        if not idx.exists():
            idx.create(overwrite=False)
        return idx

    def lookup(self, user_input: str) -> Optional[str]:
        try:
            from redisvl.query import VectorQuery
            from redisvl.query.filter import Tag

            idx = self._index()
            query_intent = classify_intent(user_input)
            vector = self.embeddings.embed_query(user_input)
            results = idx.query(
                VectorQuery(
                    vector=vector,
                    vector_field_name="prompt_vector",
                    return_fields=["prompt", "response", "intent"],
                    num_results=3,
                    filter_expression=Tag("intent") == query_intent,
                )
            )
            if not results:
                return None
            hit = results[0]
            distance = float(hit.get("vector_distance", 1.0))
            if distance >= self.threshold:
                return None
            print(
                f"[CACHE HIT redis] intent={query_intent} dist={distance:.4f}",
                flush=True,
            )
            return hit["response"]
        except Exception as e:
            print(f"[AVISO] Redis cache: {e}", flush=True)
            return None

    def store(self, user_input: str, response_text: str) -> None:
        try:
            import numpy as np

            idx = self._index()
            vector = self.embeddings.embed_query(user_input)
            idx.load(
                [
                    {
                        "prompt": user_input,
                        "response": response_text,
                        "intent": classify_intent(user_input),
                        "prompt_vector": np.array(
                            vector, dtype=np.float32
                        ).tobytes(),
                    }
                ]
            )
            print(f"[CACHE STORE redis] {user_input[:40]!r}...", flush=True)
        except Exception as e:
            print(f"[AVISO] Redis store: {e}", flush=True)


def create_semantic_cache(
    *,
    dev_mode: bool,
    embeddings: Any,
    redis_url: str,
    cache_path: str,
    distance_threshold: float,
) -> Optional[SemanticCacheBackend]:
    if not embeddings:
        return None
    if dev_mode:
        print(f"[INFO] Cache dev (JSON): {cache_path}", flush=True)
        return DevSemanticCache(embeddings, cache_path, distance_threshold)
    print("[INFO] Cache RedisVL.", flush=True)
    return RedisSemanticCache(embeddings, redis_url, distance_threshold)
