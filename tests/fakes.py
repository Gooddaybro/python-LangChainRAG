class FakeEmbeddings:
    """Deterministic embedding adapter for tests that must never call Jina."""

    def __init__(self, dimension=2048):
        self.dimension = dimension
        self.document_batches = []
        self.queries = []

    def embed_documents(self, texts):
        values = list(texts)
        self.document_batches.append(values)
        return [self._vector(text) for text in values]

    def embed_query(self, text):
        self.queries.append(text)
        return self._vector(text)

    def _vector(self, text):
        vector = [0.0] * self.dimension
        for index, byte in enumerate(text.encode("utf-8")):
            vector[index % self.dimension] += (byte + 1) / 256
        return vector
