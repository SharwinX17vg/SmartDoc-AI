from typing import Protocol

from sklearn.feature_extraction.text import TfidfVectorizer


class EmbeddingProvider(Protocol):
    def fit_transform(self, texts: list[str]): ...

    def transform(self, texts: list[str]): ...


class TfidfEmbeddingModel:
    """Local sparse embedding adapter for the Version 1 development index."""

    def __init__(self) -> None:
        self.vectorizer = TfidfVectorizer(stop_words="english", ngram_range=(1, 2))

    def fit_transform(self, texts: list[str]):
        return self.vectorizer.fit_transform(texts)

    def transform(self, texts: list[str]):
        return self.vectorizer.transform(texts)
