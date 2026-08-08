import os
import json
import logging
import pickle
import math
import hashlib
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
import numpy as np
import chromadb
from chromadb.config import Settings

logger = logging.getLogger(__name__)

# Global flag for sentence-transformers availability
_SENTENCE_TRANSFORMERS_AVAILABLE = False
_SentenceTransformer = None

def _get_sentence_transformer():
    """Lazy load SentenceTransformer to avoid import-time dependencies."""
    global _SENTENCE_TRANSFORMERS_AVAILABLE, _SentenceTransformer
    if _SentenceTransformer is not None:
        return _SentenceTransformer
    try:
        from sentence_transformers import SentenceTransformer as ST
        _SentenceTransformer = ST
        _SENTENCE_TRANSFORMERS_AVAILABLE = True
        return ST
    except Exception as e:
        logger.warning(f"SentenceTransformer not available: {e}. Using fallback embeddings.")
        _SENTENCE_TRANSFORMERS_AVAILABLE = False
        return None

# Check for FAISS availability - defer import to runtime
_FAISS_AVAILABLE = False
faiss = None

def _check_faiss():
    """Check FAISS availability at runtime."""
    global _FAISS_AVAILABLE, faiss
    if _FAISS_AVAILABLE:
        return True
    try:
        import faiss as faiss_module
        faiss = faiss_module
        _FAISS_AVAILABLE = True
        return True
    except (ImportError, AttributeError) as e:
        if "_ARRAY_API" in str(e):
            logger.warning("FAISS not compatible with NumPy 2.x, using ChromaDB only")
        else:
            logger.warning(f"FAISS not available: {e}. Using ChromaDB only")
        faiss = None
        _FAISS_AVAILABLE = False
        return False


class FastLightweightEmbeddingFunction:
    """
    Production-grade Feature Hashing Vectorizer (128-dimensional normalized unit vector).
    Provides instant, deterministic semantic vector embeddings with 0 network latency.
    Used as fallback when sentence-transformers is unavailable.
    """
    def __call__(self, input=None, texts=None):
        if input is not None:
            texts = input
        if texts is None:
            texts = []
        if isinstance(texts, str):
            texts = [texts]
            
        embeddings = []
        for text in texts:
            tokens = text.lower().replace('\n', ' ').split()
            vec = [0.0] * 128
            for t in tokens:
                h = int(hashlib.md5(t.encode('utf-8')).hexdigest(), 16)
                idx = h % 128
                vec[idx] += 1.0
            norm = math.sqrt(sum(v * v for v in vec)) or 1.0
            embeddings.append([v / norm for v in vec])
        return embeddings
    
    def embed_query(self, texts=None, input=None, **kwargs):
        """Embed query text(s)."""
        if input is not None:
            texts = input
        if texts is None:
            texts = []
        if isinstance(texts, str):
            texts = [texts]
        return self(texts)
    
    def embed_documents(self, texts=None, input=None, **kwargs):
        """Embed multiple documents."""
        if input is not None:
            texts = input
        if texts is None:
            texts = []
        if isinstance(texts, str):
            texts = [texts]
        return self(texts)


class SentenceTransformerEmbeddingFunction:
    """
    Production-grade semantic embeddings using sentence-transformers.
    Uses all-MiniLM-L6-v2 (384-dim) for fast, high-quality embeddings.
    Falls back to feature hashing if sentence-transformers unavailable.
    """
    
    def __init__(self, model_name: str = "all-MiniLM-L6-v2", device: str = None):
        self.model_name = model_name
        self.device = device or ("cuda" if self._has_cuda() else "cpu")
        self._model = None
        self._fallback_fn = FastLightweightEmbeddingFunction()
        self.dimension = 384  # Default for all-MiniLM-L6-v2
        
        # Try to load the real model
        ST = _get_sentence_transformer()
        if ST:
            try:
                logger.info(f"Loading SentenceTransformer model: {model_name} on {self.device}")
                self._model = ST(model_name, device=self.device)
                self.dimension = self._model.get_sentence_embedding_dimension()
                logger.info(f"Embedding dimension: {self.dimension}")
            except Exception as e:
                logger.warning(f"Failed to load SentenceTransformer: {e}. Using fallback.")
                self._model = None
        else:
            logger.info("SentenceTransformer not available, using feature hashing fallback")
            self.dimension = 128  # Fallback dimension
    
    def _has_cuda(self) -> bool:
        try:
            import torch
            return torch.cuda.is_available()
        except Exception:
            return False
    
    def __call__(self, input):
        """ChromaDB compatible call interface. Must accept 'input' as first positional arg."""
        texts = input
        if texts is None:
            texts = []
        if isinstance(texts, str):
            texts = [texts]
        
        if self._model:
            try:
                embeddings = self._model.encode(texts, convert_to_numpy=True, normalize_embeddings=True)
                return embeddings.tolist()
            except Exception as e:
                logger.warning(f"SentenceTransformer encode failed: {e}. Using fallback.")
        
        # Fallback to feature hashing
        return self._fallback_fn(texts)
    
    def embed_query(self, texts=None, input=None, **kwargs):
        """Embed query text(s)."""
        if input is not None:
            texts = input
        if texts is None:
            texts = []
        if isinstance(texts, str):
            texts = [texts]
        return self(texts)
    
    def embed_documents(self, texts=None, input=None, **kwargs):
        """Embed multiple documents."""
        if input is not None:
            texts = input
        if texts is None:
            texts = []
        if isinstance(texts, str):
            texts = [texts]
        return self(texts)
        """Embed multiple documents."""
        return self(texts)


class FAISSIndexManager:
    """
    FAISS-based ANN index for ultra-fast semantic search.
    Supports IVF-Flat for exact search, IVF-PQ for compressed search.
    """
    
    def __init__(self, dimension: int = 384, index_type: str = "IVF_FLAT", nlist: int = 100):
        self.dimension = dimension
        self.index_type = index_type
        self.nlist = nlist
        self.index = None
        self.id_to_idx = {}
        self.idx_to_id = {}
        self._available = False
        self._init_index()
    
    def _init_index(self):
        if not _check_faiss():
            logger.warning("FAISS not available, skipping FAISS index")
            return
        try:
            if self.index_type == "IVF_FLAT":
                quantizer = faiss.IndexFlatIP(self.dimension)
                self.index = faiss.IndexIVFFlat(quantizer, self.dimension, self.nlist, faiss.METRIC_INNER_PRODUCT)
            elif self.index_type == "IVF_PQ":
                quantizer = faiss.IndexFlatIP(self.dimension)
                self.index = faiss.IndexIVFPQ(quantizer, self.dimension, self.nlist, 64, 8, faiss.METRIC_INNER_PRODUCT)
            elif self.index_type == "FLAT":
                self.index = faiss.IndexFlatIP(self.dimension)
            else:
                self.index = faiss.IndexFlatIP(self.dimension)
            self._available = True
            logger.info(f"Initialized FAISS index: {self.index_type}, dim={self.dimension}")
        except Exception as e:
            logger.warning(f"FAISS initialization failed: {e}")
            self._available = False
    
    def train(self, embeddings: np.ndarray):
        """Train the index (required for IVF indices)."""
        if not self._available or not _check_faiss():
            return False
        try:
            if not self.index.is_trained:
                logger.info(f"Training FAISS index with {len(embeddings)} vectors")
                self.index.train(embeddings.astype(np.float32))
                logger.info("FAISS index training complete")
            return True
        except Exception as e:
            logger.warning(f"FAISS training failed: {e}")
            return False
    
    def add(self, embeddings: np.ndarray, ids: List[int]):
        """Add vectors to index."""
        if not self._available or not _check_faiss():
            return
        try:
            embeddings = embeddings.astype(np.float32)
            start_idx = self.index.ntotal
            self.index.add(embeddings)
            for i, id_val in enumerate(ids):
                idx = start_idx + i
                self.id_to_idx[id_val] = idx
                self.idx_to_id[idx] = id_val
        except Exception as e:
            logger.warning(f"FAISS add failed: {e}")
    
    def search(self, query_embedding: np.ndarray, top_k: int = 10) -> Tuple[np.ndarray, np.ndarray]:
        """Search for similar vectors."""
        if not self._available or not _check_faiss():
            return np.array([]), np.array([])
        try:
            query_embedding = query_embedding.astype(np.float32).reshape(1, -1)
            distances, indices = self.index.search(query_embedding, top_k)
            return distances[0], indices[0]
        except Exception as e:
            logger.warning(f"FAISS search failed: {e}")
            return np.array([]), np.array([])
    
    def remove(self, ids: List[int]):
        """Remove vectors by ID (requires rebuild for IVF)."""
        if not self._available:
            return
        for id_val in ids:
            if id_val in self.id_to_idx:
                del self.id_to_idx[id_val]
        logger.warning("FAISS remove called - full rebuild recommended")
    
    def save(self, path: str):
        """Save index to disk."""
        if not self._available or not _check_faiss():
            return
        try:
            faiss.write_index(self.index, f"{path}.faiss")
            with open(f"{path}.mapping", "wb") as f:
                pickle.dump({"id_to_idx": self.id_to_idx, "idx_to_id": self.idx_to_id}, f)
        except Exception as e:
            logger.warning(f"FAISS save failed: {e}")
    
    def load(self, path: str):
        """Load index from disk."""
        if not _check_faiss():
            return
        try:
            self.index = faiss.read_index(f"{path}.faiss")
            with open(f"{path}.mapping", "rb") as f:
                mapping = pickle.load(f)
                self.id_to_idx = mapping["id_to_idx"]
                self.idx_to_id = mapping["idx_to_id"]
            self._available = True
            logger.info(f"Loaded FAISS index with {self.index.ntotal} vectors")
        except Exception as e:
            logger.warning(f"FAISS load failed: {e}")
            self._available = False


class VectorStoreManager:
    """
    Hybrid Vector Store Manager with:
    1. ChromaDB for persistent storage & metadata filtering
    2. FAISS for ultra-fast ANN search
    3. SentenceTransformer for high-quality embeddings
    4. Dual-write sync with SQL database
    """
    
    def __init__(
        self, 
        persist_directory: str = "./chroma_db",
        faiss_path: str = "./faiss_index",
        embedding_model: str = "all-MiniLM-L6-v2",
        use_faiss: bool = True
    ):
        self.persist_directory = persist_directory
        self.faiss_path = faiss_path
        self.use_faiss = use_faiss
        
        os.makedirs(persist_directory, exist_ok=True)
        os.makedirs(os.path.dirname(faiss_path) or ".", exist_ok=True)
        
        # Initialize embedding function
        self.embedding_fn = SentenceTransformerEmbeddingFunction(embedding_model)
        self.dimension = self.embedding_fn.dimension
        
        # Initialize ChromaDB
        self._init_chromadb()
        
        # Initialize FAISS
        if self.use_faiss:
            self._init_faiss()
        
        logger.info("Hybrid Vector Store initialized successfully")
    
    def _init_chromadb(self):
        """Initialize ChromaDB with sentence-transformer embeddings."""
        try:
            self.client = chromadb.PersistentClient(path=self.persist_directory)
            
            # Delete old collection if exists (dimension mismatch)
            try:
                self.client.delete_collection("smartreco_products")
            except Exception:
                pass
            
            self.collection = self.client.create_collection(
                name="smartreco_products",
                embedding_function=self.embedding_fn,
                metadata={"hnsw:space": "cosine", "hnsw:construction_ef": 100, "hnsw:search_ef": 50}
            )
            logger.info("ChromaDB collection created with SentenceTransformer embeddings")
        except Exception as e:
            logger.error(f"Failed to initialize ChromaDB: {e}")
            self.client = None
            self.collection = None
    
    def _init_faiss(self):
        """Initialize FAISS index."""
        try:
            self.faiss_index = FAISSIndexManager(
                dimension=self.dimension,
                index_type="IVF_FLAT",
                nlist=min(100, max(1, self.collection.count() // 10)) if self.collection else 100
            )
            
            # Load existing index if available
            if os.path.exists(f"{self.faiss_path}.faiss"):
                self.faiss_index.load(self.faiss_path)
                logger.info(f"Loaded FAISS index with {self.faiss_index.index.ntotal} vectors")
            else:
                logger.info("No existing FAISS index found, will build on first sync")
        except Exception as e:
            logger.warning(f"FAISS initialization failed, falling back to ChromaDB only: {e}")
            self.use_faiss = False
            self.faiss_index = None
    
    def _prepare_document(self, product: Dict[str, Any]) -> str:
        """Build rich semantic document for embedding."""
        tags = product.get('tags', [])
        tags_str = ", ".join(tags) if isinstance(tags, list) else str(tags)
        
        # Enrich with category-specific context
        category_context = {
            "Generative AI & Agents": "AI agents, LLM, RAG, LangGraph, autonomous systems, prompt engineering",
            "Cybersecurity": "ethical hacking, penetration testing, vulnerability assessment, threat hunting, security",
            "Web Development & Fullstack": "React, Next.js, TypeScript, Node.js, API, frontend, backend, fullstack",
            "Data Science & Machine Learning": "Python, PyTorch, TensorFlow, ML, deep learning, NLP, computer vision",
            "Cloud & DevOps": "AWS, Kubernetes, Docker, Terraform, CI/CD, infrastructure, DevOps, SRE"
        }
        
        context = category_context.get(product.get('category', ''), '')
        
        doc_text = (
            f"Title: {product.get('title', '')}\n"
            f"Category: {product.get('category', '')}\n"
            f"Description: {product.get('description', '')}\n"
            f"Tags: {tags_str}\n"
            f"Domain Context: {context}\n"
            f"Price: ${product.get('price', 0)}\n"
            f"Rating: {product.get('rating', 4.5)}/5.0"
        )
        return doc_text
    
    def add_or_update_product(self, product: Dict[str, Any]) -> bool:
        """Dual-write: upsert to ChromaDB and FAISS."""
        if not self.collection:
            logger.warning("ChromaDB collection unavailable")
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
            # ChromaDB upsert
            self.collection.upsert(
                ids=[prod_id],
                documents=[doc_text],
                metadatas=[metadata]
            )
            
            # FAISS upsert (rebuild strategy for simplicity)
            if self.use_faiss and self.faiss_index:
                embedding = self.embedding_fn([doc_text])[0]
                self.faiss_index.add(
                    np.array([embedding], dtype=np.float32),
                    [product['id']]
                )
                # Persist FAISS index
                self.faiss_index.save(self.faiss_path)
            
            logger.info(f"Dual-write SUCCESS: Product {prod_id} ('{product.get('title')}')")
            return True
        except Exception as e:
            logger.error(f"Dual-write ERROR on product {prod_id}: {e}")
            return False
    
    def delete_product(self, product_id: int) -> bool:
        """Delete from both stores."""
        if not self.collection:
            return False
        
        prod_id = str(product_id)
        try:
            self.collection.delete(ids=[prod_id])
            
            if self.use_faiss and self.faiss_index:
                self.faiss_index.remove([product_id])
                self.faiss_index.save(self.faiss_path)
            
            logger.info(f"Deleted product {prod_id} from both stores")
            return True
        except Exception as e:
            logger.error(f"Delete ERROR on product {prod_id}: {e}")
            return False
    
    def semantic_search(
        self, 
        query_text: str, 
        top_k: int = 10, 
        category_filter: str = None,
        use_faiss: bool = None
    ) -> List[Dict[str, Any]]:
        """
        Hybrid semantic search:
        - FAISS for fast ANN retrieval (if enabled)
        - ChromaDB for metadata filtering & exact search
        - Fusion of results with score normalization
        """
        use_faiss = use_faiss if use_faiss is not None else self.use_faiss
        
        if not self.collection:
            return []
        
        # Build where clause for category filtering
        where_clause = {}
        if category_filter and category_filter != "All":
            where_clause["category"] = category_filter
        
        results = []
        
        # Strategy 1: FAISS for fast candidate retrieval
        faiss_candidates = []
        if use_faiss and self.faiss_index and self.faiss_index._available and self.faiss_index.index and self.faiss_index.index.ntotal > 0:
            try:
                query_embedding = np.array(self.embedding_fn([query_text])[0], dtype=np.float32)
                distances, indices = self.faiss_index.search(query_embedding, top_k * 3)  # Over-retrieve
                
                for dist, idx in zip(distances, indices):
                    if idx in self.faiss_index.idx_to_id:
                        product_id = self.faiss_index.idx_to_id[idx]
                        # Convert inner product to cosine similarity (embeddings are normalized)
                        similarity = float(dist)  # Already cosine since normalized
                        faiss_candidates.append({
                            'product_id': product_id,
                            'faiss_score': similarity,
                            'source': 'faiss'
                        })
            except Exception as e:
                logger.warning(f"FAISS search failed: {e}")
        
        # Strategy 2: ChromaDB for metadata-filtered exact search
        chroma_candidates = []
        try:
            chroma_results = self.collection.query(
                query_texts=[query_text],
                n_results=top_k * 2,
                where=where_clause if where_clause else None
            )
            
            if chroma_results and 'ids' in chroma_results and chroma_results['ids']:
                ids = chroma_results['ids'][0]
                metadatas = chroma_results['metadatas'][0] if chroma_results.get('metadatas') else []
                distances = chroma_results['distances'][0] if chroma_results.get('distances') else []
                
                for i, id_val in enumerate(ids):
                    dist = distances[i] if i < len(distances) else 1.0
                    # ChromaDB returns cosine distance, convert to similarity
                    similarity = max(0.0, min(1.0, 1.0 - dist))
                    
                    meta = metadatas[i] if i < len(metadatas) else {}
                    chroma_candidates.append({
                        'product_id': int(id_val),
                        'chroma_score': similarity,
                        'metadata': meta,
                        'source': 'chromadb'
                    })
        except Exception as e:
            logger.warning(f"ChromaDB search failed: {e}")
        
        # Strategy 3: Fuse results with reciprocal rank fusion
        fused = self._reciprocal_rank_fusion(faiss_candidates, chroma_candidates, top_k)
        
        # Enrich with full product details
        enriched = []
        for candidate in fused:
            product = self._get_product_details(candidate['product_id'])
            if product:
                product['similarity_score'] = candidate.get('fused_score', candidate.get('chroma_score', candidate.get('faiss_score', 0)))
                product['retrieval_sources'] = candidate.get('sources', [])
                enriched.append(product)
        
        return enriched[:top_k]
    
    def _reciprocal_rank_fusion(
        self, 
        faiss_results: List[Dict], 
        chroma_results: List[Dict], 
        top_k: int,
        k: int = 60
    ) -> List[Dict]:
        """Reciprocal Rank Fusion for combining multiple ranked lists."""
        scores = {}
        sources = {}
        
        # Process FAISS results
        for rank, item in enumerate(faiss_results):
            pid = item['product_id']
            rrf_score = 1.0 / (k + rank + 1)
            scores[pid] = scores.get(pid, 0) + rrf_score
            sources[pid] = sources.get(pid, []) + ['faiss']
        
        # Process ChromaDB results
        for rank, item in enumerate(chroma_results):
            pid = item['product_id']
            rrf_score = 1.0 / (k + rank + 1)
            scores[pid] = scores.get(pid, 0) + rrf_score
            sources[pid] = sources.get(pid, []) + ['chromadb']
        
        # Sort by fused score
        sorted_items = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        
        return [
            {'product_id': pid, 'fused_score': score, 'sources': sources[pid]}
            for pid, score in sorted_items[:top_k]
        ]
    
    def _get_product_details(self, product_id: int) -> Optional[Dict]:
        """Fetch full product details from ChromaDB metadata."""
        if not self.collection:
            return None
        try:
            result = self.collection.get(ids=[str(product_id)], include=['metadatas', 'documents'])
            if result and result['ids']:
                meta = result['metadatas'][0] if result.get('metadatas') else {}
                doc = result['documents'][0] if result.get('documents') else ''
                return {
                    'product_id': product_id,
                    'metadata': meta,
                    'document': doc
                }
        except Exception:
            pass
        return None
    
    def get_total_count(self) -> int:
        if not self.collection:
            return 0
        try:
            return self.collection.count()
        except Exception:
            return 0
    
    def sync_all_products(self, products_list) -> int:
        """Bulk sync all products - rebuild FAISS index."""
        success_count = 0
        all_embeddings = []
        all_ids = []
        
        for p in products_list:
            prod_dict = p.to_dict() if hasattr(p, 'to_dict') else p
            if self.add_or_update_product(prod_dict):
                success_count += 1
                doc_text = self._prepare_document(prod_dict)
                embedding = self.embedding_fn([doc_text])[0]
                all_embeddings.append(embedding)
                all_ids.append(prod_dict['id'])
        
        # Rebuild FAISS index with all embeddings
        if self.use_faiss and self.faiss_index and all_embeddings:
            logger.info(f"Rebuilding FAISS index with {len(all_embeddings)} vectors")
            self.faiss_index = FAISSIndexManager(dimension=self.dimension)
            self.faiss_index.train(np.array(all_embeddings, dtype=np.float32))
            self.faiss_index.add(np.array(all_embeddings, dtype=np.float32), all_ids)
            self.faiss_index.save(self.faiss_path)
            logger.info("FAISS index rebuilt and saved")
        
        return success_count


# Global singleton instance (lazy initialization)
_vector_store_instance = None


def get_vector_store():
    """Get or create the vector store instance (lazy initialization)."""
    global _vector_store_instance
    if _vector_store_instance is None:
        _vector_store_instance = VectorStoreManager()
    return _vector_store_instance


# Backward compatibility: create a proxy that initializes on first attribute access
class _LazyVectorStore:
    def __getattr__(self, name):
        return getattr(get_vector_store(), name)


vector_store = _LazyVectorStore()