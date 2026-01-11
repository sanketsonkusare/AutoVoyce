from abc import ABC, abstractmethod

class VectorIndexStrategy(ABC):

    @abstractmethod
    def create_or_load_vector_index(self, markdown_text: str, chunker=None, namespace: str = None):
        pass

    @abstractmethod
    def semantic_search(self, embeded_query: list[float], namespace: str = None) -> str:
        pass
