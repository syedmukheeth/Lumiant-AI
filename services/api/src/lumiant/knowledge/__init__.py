"""Knowledge retrieval for the assistant: definitions, methods, policies and terminology (Product v2, P2; RAG v2).

Holds meanings, never figures about a customer's stock: those always come from the query engine (ADR-0002).
"""

from lumiant.knowledge.index import Chunk, Embedder, Hit, KnowledgeIndex, product_index, tenant_index

__all__ = ["Chunk", "Embedder", "Hit", "KnowledgeIndex", "product_index", "tenant_index"]
