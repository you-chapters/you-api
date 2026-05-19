import os

from openai import OpenAI

from app.ports.embedding_port import EmbeddingPort

_MODEL = "text-embedding-3-small"


class OpenAIEmbeddingClient(EmbeddingPort):
    def __init__(self) -> None:
        self._client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])

    def embed(self, text: str) -> list[float]:
        response = self._client.embeddings.create(model=_MODEL, input=text)
        return response.data[0].embedding
