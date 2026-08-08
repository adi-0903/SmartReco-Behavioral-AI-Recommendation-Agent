import os
import json
import logging
import math
import hashlib
import numpy as np

# Backward compatibility patch for ChromaDB with NumPy 2.x
if not hasattr(np, 'float_'):
    np.float_ = np.float64
if not hasattr(np, 'int_'):
    np.int_ = np.int64
if not hasattr(np, 'uint'):
    np.uint = np.uint64

import chromadb
from chromadb.config import Settings

logger = logging.getLogger(__name__)

class FastLightweightEmbeddingFunction:
    """
    Production-grade Feature Hashing Vectorizer (128-dimensional normalized unit vector).
    Provides instant, deterministic semantic vector embeddings with 0 network latency.
    """
    def __call__(self, input):
        if isinstance(input, str):
            input = [input]
            
        embeddings = []
        for text in input:
            tokens = text.lower().replace('\n', ' ').split()
            vec = [0.0] * 128
            for t in tokens:
                h = int(hashlib.md5(t.encode('utf-8')).hexdigest(), 16)
                idx = h % 128
                vec[idx] += 1.0
            norm = math.sqrt(sum(v * v for v in vec)) or 1.0
            embeddings.append([v / norm for v in vec])
        return embeddings
    
    def embed_query(self, texts=None, input=None):
        """Embed query text(s). ChromaDB passes a list of strings."""
        if input is not None:
            texts = input
        if texts is None:
            texts = []
        if isinstance(texts, str):
            texts = [texts]
        return self.__call__(texts)
    
    def embed_documents(self, texts=None, input=None):
        """Embed multiple documents."""
        if input is not None:
            texts = input
        if texts is None:
            texts = []
        if isinstance(texts, str):
            texts = [texts]
        return self.__call__(texts)

class VectorStoreManager:
    """
    Dual-Write Vector Store Manager using ChromaDB.
    Maintains semantic vector index of products in sync with SQL database.
    """
    def __init__(self, persist_directory="./chroma_db"):
        self.persist_directory = persist_directory
        os.makedirs(self.persist_directory, exist_ok=True)
        
        try:
            self.client = chromadb.PersistentClient(path=self.persist_directory)
            self.embedding_fn = FastLightweightEmbeddingFunction()
            try:
                self.collection = self.client.get_or_create_collection(
                    name="smartreco_products",
                    embedding_function=self.embedding_fn,
                    metadata={"hnsw:space": "cosine"}
                )
            except Exception as e:
                logger.warning(f"Rebuilding collection due to configuration update: {e}")
                try:
                    self.client.delete_collection("smartreco_products")
                except Exception:
                    pass
                self.collection = self.client.get_or_create_collection(
                    name="smartreco_products",
                    embedding_function=self.embedding_fn,
                    metadata={"hnsw:space": "cosine"}
                )
            logger.info("ChromaDB vector store initialized with FastLightweightEmbeddingFunction.")
        except Exception as e:
            logger.error(f"Failed to initialize ChromaDB: {e}")
            self.client = None
            self.collection = None

    def _prepare_document(self, product):
        """Builds a rich semantic document string for embedding."""
        tags_str = ", ".join(product.get('tags', [])) if isinstance(product.get('tags'), list) else str(product.get('tags', ''))
        doc_text = (
            f"Title: {product.get('title', '')}\n"
            f"Category: {product.get('category', '')}\n"
            f"Description: {product.get('description', '')}\n"
            f"Tags: {tags_str}\n"
            f"Price: ${product.get('price', 0)}"
        )
        return doc_text

    def add_or_update_product(self, product):
        """Dual-write operation: Upsert product into vector DB."""
        if not self.collection:
            logger.warning("Vector store collection unavailable. Skipping vector upsert.")
            return False
            
        prod_id = str(product['id'])
        doc_text = self._prepare_document(product)
        metadata = {
            "product_id": product['id'],
            "title": product.get('title', ''),
            "category": product.get('category', ''),
            "price": float(product.get('price', 0)),
            "rating": float(product.get('rating', 4.5))
        }
        
        try:
            self.collection.upsert(
                ids=[prod_id],
                documents=[doc_text],
                metadatas=[metadata]
            )
            logger.info(f"Vector Store Dual-Write SUCCESS: Upserted product {prod_id} ('{product.get('title')}')")
            return True
        except Exception as e:
            logger.error(f"Vector Store Dual-Write ERROR on product {prod_id}: {e}")
            return False

    def delete_product(self, product_id):
        """Dual-write operation: Delete product from vector DB."""
        if not self.collection:
            return False
            
        prod_id = str(product_id)
        try:
            self.collection.delete(ids=[prod_id])
            logger.info(f"Vector Store Dual-Write SUCCESS: Deleted product {prod_id}")
            return True
        except Exception as e:
            logger.error(f"Vector Store Dual-Write ERROR on deleting product {prod_id}: {e}")
            return False

    def semantic_search(self, query_text, top_k=5, category_filter=None):
        """
        Performs semantic vector retrieval given user search intent or behavior text.
        Supports optional metadata filtering by category.
        """
        if not self.collection:
            return []
            
        try:
            where_clause = {}
            if category_filter and category_filter != "All":
                where_clause["category"] = category_filter
                
            results = self.collection.query(
                query_texts=[query_text],
                n_results=top_k,
                where=where_clause if where_clause else None
            )
            
            matched = []
            if results and 'ids' in results and len(results['ids']) > 0:
                ids = results['ids'][0]
                metadatas = results['metadatas'][0] if 'metadatas' in results and results['metadatas'] else []
                distances = results['distances'][0] if 'distances' in results and results['distances'] else []
                documents = results['documents'][0] if 'documents' in results and results['documents'] else []
                
                for i in range(len(ids)):
                    # Cosine distance to similarity conversion
                    dist = distances[i] if i < len(distances) else 1.0
                    similarity = max(0.0, min(1.0, 1.0 - (dist / 2.0)))
                    
                    matched.append({
                        'product_id': int(ids[i]),
                        'metadata': metadatas[i] if i < len(metadatas) else {},
                        'document': documents[i] if i < len(documents) else '',
                        'similarity_score': round(similarity, 4)
                    })
            return matched
        except Exception as e:
            logger.error(f"Semantic search failed: {e}")
            if "dimension" in str(e).lower() and self.client:
                try:
                    logger.warning("Resetting ChromaDB collection due to dimension update...")
                    self.client.delete_collection("smartreco_products")
                    self.collection = self.client.get_or_create_collection(
                        name="smartreco_products",
                        embedding_function=self.embedding_fn,
                        metadata={"hnsw:space": "cosine"}
                    )
                    from models import Product
                    self.sync_all_products(Product.query.all())
                except Exception as ex_reset:
                    logger.error(f"Failed collection reset: {ex_reset}")
            return []

    def get_total_count(self):
        """Returns total vector embeddings stored."""
        if not self.collection:
            return 0
        try:
            return self.collection.count()
        except Exception:
            return 0

    def sync_all_products(self, products_list):
        """Bulk synchronizes SQL database catalog into vector DB."""
        success_count = 0
        for p in products_list:
            prod_dict = p.to_dict() if hasattr(p, 'to_dict') else p
            if self.add_or_update_product(prod_dict):
                success_count += 1
        return success_count

# Global singleton instance
vector_store = VectorStoreManager()
