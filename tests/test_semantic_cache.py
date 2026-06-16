import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from app.services.semantic_cache import DevSemanticCache, create_semantic_cache


@pytest.fixture
def mock_embeddings():
    emb = MagicMock()
    emb.embed_query.return_value = [1.0, 0.0, 0.0]
    return emb


def test_dev_cache_store_and_hit(tmp_path, mock_embeddings):
    cache_file = tmp_path / "cache.json"
    cache = DevSemanticCache(
        mock_embeddings, str(cache_file), distance_threshold=0.5
    )
    cache.store("onde fica o napsi", '{"response": "Bloco A", "emotion": "calm"}')

    mock_embeddings.embed_query.return_value = [1.0, 0.0, 0.0]
    hit = cache.lookup("onde fica o NAPSI")
    assert hit is not None
    assert "Bloco A" in hit
    assert cache_file.exists()
    data = json.loads(cache_file.read_text(encoding="utf-8"))
    assert len(data) == 1


def test_dev_cache_miss_on_distance(tmp_path, mock_embeddings):
    cache_file = tmp_path / "cache.json"
    cache = DevSemanticCache(
        mock_embeddings, str(cache_file), distance_threshold=0.01
    )
    cache.store("pergunta A", "resposta A")
    mock_embeddings.embed_query.return_value = [0.0, 1.0, 0.0]
    assert cache.lookup("pergunta totalmente diferente") is None


def test_create_semantic_cache_dev(mock_embeddings):
    backend = create_semantic_cache(
        dev_mode=True,
        embeddings=mock_embeddings,
        redis_url="redis://localhost:6379",
        cache_path="./data/test_cache.json",
        distance_threshold=0.12,
    )
    assert isinstance(backend, DevSemanticCache)


def test_dev_cache_miss_different_intent(tmp_path, mock_embeddings):
    cache_file = tmp_path / "cache.json"
    cache = DevSemanticCache(
        mock_embeddings, str(cache_file), distance_threshold=0.99
    )
    cache.store("Como agendar atendimento?", '{"response": "E-mail napsi@poli.br"}')
    mock_embeddings.embed_query.return_value = [1.0, 0.0, 0.0]
    assert cache.lookup("Onde fica o NAPSI?") is None


def test_create_semantic_cache_no_embeddings():
    assert (
        create_semantic_cache(
            dev_mode=True,
            embeddings=None,
            redis_url="redis://localhost:6379",
            cache_path="./data/x.json",
            distance_threshold=0.12,
        )
        is None
    )
