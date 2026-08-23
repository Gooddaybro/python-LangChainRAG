import pytest

from clothing_assistant.infrastructure import vector_store


@pytest.fixture(autouse=True)
def block_unpatched_jina_requests(monkeypatch):
    """Fail tests that reach Jina without explicitly replacing the adapter boundary."""

    def fail_live_request(*_args, **_kwargs):
        raise AssertionError("tests must inject an embedding adapter instead of calling Jina")

    vector_store._EMBEDDINGS_CACHE = None
    monkeypatch.setattr(vector_store.httpx, "post", fail_live_request)
    yield
    vector_store._EMBEDDINGS_CACHE = None
