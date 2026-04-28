from types import SimpleNamespace

from app.services.embedding_service import EmbeddingService


class FakeEmbeddings:
    def create(self, **kwargs):
        assert kwargs["model"]
        assert kwargs["dimensions"] == 1536
        return SimpleNamespace(
            data=[
                SimpleNamespace(embedding=[0.1] * 1536),
                SimpleNamespace(embedding=[0.2] * 1536),
            ]
        )


class FakeClient:
    embeddings = FakeEmbeddings()


def test_embedding_service_returns_vectors():
    service = EmbeddingService(client=FakeClient())

    vectors = service.embed_texts(["first", "second"])

    assert len(vectors) == 2
    assert len(vectors[0]) == 1536

