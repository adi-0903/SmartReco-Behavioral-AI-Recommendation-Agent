"""
Advanced Recommender Service for SmartReco
Implements hybrid retrieval, LightGBM ranking, MMR diversity, and real-time learning.
"""

import os
import json
import logging
import pickle
import time
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import lightgbm as lgb
from scipy.sparse import csr_matrix
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from config import Config
from models import db, User, Product, Event, Recommendation, UserFeedback, UserProfile, ProductSimilarity, RecommendationImpression, RankingModel, ABTestAssignment
from vector_store import get_vector_store

logger = logging.getLogger(__name__)


@dataclass
class RetrievalResult:
    product_id: int
    score: float
    source: str  # semantic, collaborative, popularity, content, quiz
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class RankedRecommendation:
    product_id: int
    final_score: float
    retrieval_scores: Dict[str, float]
    ranker_score: float
    diversity_penalty: float
    explanation: str = ""


class CollaborativeFilteringEngine:
    """
    Item-item collaborative filtering using implicit feedback (ALS-style).
    Computes product similarities from user interaction matrix.
    """
    
    def __init__(self):
        self.item_factors = None
        self.user_factors = None
        self.product_id_to_idx = {}
        self.idx_to_product_id = {}
        self.interaction_matrix = None
        self.last_trained = None
    
    def build_interaction_matrix(self, min_interactions: int = 2) -> csr_matrix:
        """Build sparse user-item interaction matrix from events and feedback."""
        # Get all implicit feedback events
        events = Event.query.filter(Event.user_id.isnot(None)).all()
        feedback = UserFeedback.query.filter(
            UserFeedback.feedback_type.in_([
                'implicit_click', 'implicit_dwell', 'implicit_enroll',
                'explicit_like', 'explicit_dislike'
            ])
        ).all()
        
        # Collect all user-item interactions
        interactions = {}
        
        # Weight different event types
        event_weights = {
            'search': 0.5,
            'product_view': 1.0,
            'dwell_time': 0.1,  # per 10 seconds
            'click_recommendation': 2.0,
            'enroll_click': 3.0,
            'category_filter': 0.3
        }
        
        for event in events:
            if event.target_id and event.target_id.isdigit():
                pid = int(event.target_id)
                uid = event.user_id
                weight = event_weights.get(event.event_type, 0.5)
                if event.event_type == 'dwell_time':
                    weight = min(event.duration_ms / 10000, 2.0)  # cap at 2.0
                key = (uid, pid)
                interactions[key] = interactions.get(key, 0) + weight
        
        # Add explicit feedback
        for fb in feedback:
            uid, pid = fb.user_id, fb.product_id
            if fb.feedback_type == 'explicit_like':
                weight = 5.0
            elif fb.feedback_type == 'explicit_dislike':
                weight = -2.0
            elif fb.feedback_type == 'implicit_enroll':
                weight = 5.0
            else:
                weight = fb.value
            key = (uid, pid)
            interactions[key] = interactions.get(key, 0) + weight
        
        # Filter users/items with minimum interactions
        user_counts = {}
        item_counts = {}
        for (uid, pid), weight in interactions.items():
            user_counts[uid] = user_counts.get(uid, 0) + 1
            item_counts[pid] = item_counts.get(pid, 0) + 1
        
        valid_users = {u for u, c in user_counts.items() if c >= min_interactions}
        valid_items = {i for i, c in item_counts.items() if c >= min_interactions}
        
        filtered = {k: v for k, v in interactions.items() 
                   if k[0] in valid_users and k[1] in valid_items}
        
        if not filtered:
            logger.warning("Insufficient interactions for collaborative filtering")
            return csr_matrix((0, 0))
        
        # Build mappings
        users = sorted(set(u for u, _ in filtered.keys()))
        items = sorted(set(i for _, i in filtered.keys()))
        
        self.user_id_to_idx = {u: i for i, u in enumerate(users)}
        self.idx_to_user_id = {i: u for i, u in enumerate(users)}
        self.product_id_to_idx = {p: i for i, p in enumerate(items)}
        self.idx_to_product_id = {i: p for i, p in enumerate(items)}
        
        # Build sparse matrix
        rows = [self.user_id_to_idx[u] for u, _ in filtered.keys()]
        cols = [self.product_id_to_idx[p] for _, p in filtered.keys()]
        data = list(filtered.values())
        
        matrix = csr_matrix((data, (rows, cols)), shape=(len(users), len(items)))
        self.interaction_matrix = matrix
        
        logger.info(f"Built interaction matrix: {matrix.shape[0]} users x {matrix.shape[1]} items, {matrix.nnz} interactions")
        return matrix
    
    def train_als(self, factors: int = 64, iterations: int = 20, regularization: float = 0.01, alpha: float = 1.0):
        """Train Alternating Least Squares model using implicit library approach."""
        try:
            from implicit.als import AlternatingLeastSquares
        except ImportError:
            logger.warning("implicit library not available, using SVD fallback")
            return self._train_svd(factors)
        
        matrix = self.interaction_matrix
        if matrix is None or matrix.nnz == 0:
            matrix = self.build_interaction_matrix()
        
        if matrix.nnz == 0:
            return False
        
        # Convert to confidence matrix (implicit feedback)
        confidence = alpha * matrix
        
        model = AlternatingLeastSquares(
            factors=factors,
            iterations=iterations,
            regularization=regularization,
            random_state=42
        )
        
        logger.info(f"Training ALS model: {factors} factors, {iterations} iterations")
        model.fit(confidence.T.tocsr())  # implicit expects item-user matrix
        
        self.item_factors = model.item_factors  # item x factors
        self.user_factors = model.user_factors  # user x factors
        self.last_trained = datetime.utcnow()
        
        logger.info(f"ALS training complete. Item factors: {self.item_factors.shape}")
        return True
    
    def _train_svd(self, factors: int) -> bool:
        """Fallback SVD using scipy."""
        from scipy.sparse.linalg import svds
        
        matrix = self.interaction_matrix
        if matrix is None or matrix.nnz == 0:
            matrix = self.build_interaction_matrix()
        
        if matrix.nnz == 0:
            return False
        
        k = min(factors, min(matrix.shape) - 1)
        U, s, Vt = svds(matrix.astype(np.float32), k=k)
        
        self.user_factors = U * np.sqrt(s)
        self.item_factors = Vt.T * np.sqrt(s)
        self.last_trained = datetime.utcnow()
        
        logger.info(f"SVD training complete. Item factors: {self.item_factors.shape}")
        return True
    
    def get_similar_items(self, product_id: int, top_k: int = 20) -> List[Tuple[int, float]]:
        """Get similar items based on learned item factors."""
        if self.item_factors is None or product_id not in self.product_id_to_idx:
            return []
        
        idx = self.product_id_to_idx[product_id]
        item_vector = self.item_factors[idx]
        
        # Compute cosine similarity with all items
        norms = np.linalg.norm(self.item_factors, axis=1)
        item_norms = norms[idx]
        all_norms = norms
        similarities = np.dot(self.item_factors, item_vector) / (all_norms * item_norms + 1e-8)
        
        # Get top-k excluding self
        similar_indices = np.argsort(similarities)[::-1][1:top_k+1]
        
        results = []
        for sim_idx in similar_indices:
            if sim_idx in self.idx_to_product_id:
                sim_pid = self.idx_to_product_id[sim_idx]
                results.append((sim_pid, float(similarities[sim_idx])))
        
        return results
    
    def get_user_recommendations(self, user_id: int, top_k: int = 20, exclude: List[int] = None) -> List[Tuple[int, float]]:
        """Get personalized recommendations for a user."""
        if self.user_factors is None or user_id not in self.user_id_to_idx:
            return []
        
        exclude = set(exclude or [])
        user_idx = self.user_id_to_idx[user_id]
        user_vector = self.user_factors[user_idx]
        
        # Score all items
        scores = np.dot(self.item_factors, user_vector)
        
        # Filter out excluded items
        item_indices = np.argsort(scores)[::-1]
        
        results = []
        for idx in item_indices:
            pid = self.idx_to_product_id.get(idx)
            if pid and pid not in exclude:
                results.append((pid, float(scores[idx])))
                if len(results) >= top_k:
                    break
        
        return results


class PopularityEngine:
    """Popularity-based recommendations with recency and category awareness."""
    
    def __init__(self):
        self.popularity_scores = {}
        self.category_popularity = {}
        self.last_updated = None
    
    def compute_popularity(self):
        """Compute popularity scores from events and enrollments."""
        # Recent events (last 30 days)
        cutoff = datetime.utcnow() - timedelta(days=30)
        recent_events = Event.query.filter(Event.timestamp >= cutoff).all()
        
        scores = {}
        cat_scores = {}
        
        # Event weights
        weights = {
            'search': 1.0,
            'product_view': 2.0,
            'dwell_time': 0.5,
            'click_recommendation': 3.0,
            'enroll_click': 5.0,
            'category_filter': 1.0
        }
        
        for event in recent_events:
            if event.target_id and event.target_id.isdigit():
                pid = int(event.target_id)
                weight = weights.get(event.event_type, 1.0)
                if event.event_type == 'dwell_time':
                    weight = min(event.duration_ms / 50000, 3.0)
                scores[pid] = scores.get(pid, 0) + weight
                
                if event.details_json:
                    try:
                        details = json.loads(event.details_json)
                        cat = details.get('category')
                        if cat:
                            cat_scores[cat] = cat_scores.get(cat, 0) + weight
                    except Exception:
                        pass
        
        # Add enrollment counts
        enrollments = Enrollment.query.all()
        for enr in enrollments:
            scores[enr.product_id] = scores.get(enr.product_id, 0) + 10.0
        
        # Normalize
        max_score = max(scores.values()) if scores else 1.0
        self.popularity_scores = {k: v / max_score for k, v in scores.items()}
        
        max_cat = max(cat_scores.values()) if cat_scores else 1.0
        self.category_popularity = {k: v / max_cat for k, v in cat_scores.items()}
        self.last_updated = datetime.utcnow()
        
        logger.info(f"Computed popularity for {len(scores)} products")
    
    def get_top_popular(self, top_k: int = 10, category: str = None) -> List[Tuple[int, float]]:
        if category and category in self.category_popularity:
            # Filter by category
            products = Product.query.filter_by(category=category).all()
            cat_products = [(p.id, self.popularity_scores.get(p.id, 0)) for p in products]
            cat_products.sort(key=lambda x: x[1], reverse=True)
            return cat_products[:top_k]
        
        sorted_scores = sorted(self.popularity_scores.items(), key=lambda x: x[1], reverse=True)
        return sorted_scores[:top_k]


class LightGBMRanker:
    """
    LightGBM Learning-to-Rank model for final recommendation ranking.
    Optimizes NDCG@K with multi-objective features.
    """
    
    def __init__(self, model_dir: str = "./models/ranker"):
        self.model_dir = Path(model_dir)
        self.model_dir.mkdir(parents=True, exist_ok=True)
        self.model = None
        self.feature_names = []
        self.is_trained = False
    
    def extract_features(
        self, 
        user_id: int, 
        product_id: int, 
        retrieval_scores: Dict[str, float],
        user_profile: Optional[UserProfile] = None,
        product: Optional[Product] = None
    ) -> np.ndarray:
        """Extract ranking features for user-product pair."""
        features = []
        
        # Retrieval scores (normalized)
        sources = ['semantic', 'collaborative', 'popularity', 'content', 'quiz']
        for src in sources:
            features.append(retrieval_scores.get(src, 0.0))
        
        # User features
        if user_profile:
            features.append(user_profile.total_events / 1000.0)  # normalized
            features.append(user_profile.ctr)
            features.append(len(user_profile.get_category_affinity()))
            features.append(len(user_profile.get_topic_affinity()))
            features.append(1.0 if user_profile.skill_level == 'advanced' else 0.5 if user_profile.skill_level == 'intermediate' else 0.0)
        else:
            features.extend([0.0] * 5)
        
        # Product features
        if product:
            features.append(product.price / 200.0)  # normalized
            features.append(product.rating / 5.0)
            features.append(len(product.tags) if product.tags else 0)
            # Category one-hot (simplified)
            categories = ['Generative AI & Agents', 'Cybersecurity', 'Web Development & Fullstack', 
                         'Data Science & Machine Learning', 'Cloud & DevOps']
            for cat in categories:
                features.append(1.0 if product.category == cat else 0.0)
        else:
            features.extend([0.0] * (3 + 5))
        
        # Cross features
        if user_profile and product:
            cat_affinity = user_profile.get_category_affinity().get(product.category, 0.0)
            features.append(cat_affinity)
            topic_overlap = len(set(user_profile.get_topic_affinity().keys()) & 
                              set(product.tags if product.tags else []))
            features.append(min(topic_overlap / 10.0, 1.0))
        else:
            features.extend([0.0, 0.0])
        
        return np.array(features, dtype=np.float32)
    
    def prepare_training_data(self) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Prepare training data from historical impressions and feedback."""
        impressions = RecommendationImpression.query.join(UserFeedback, 
            (UserFeedback.user_id == RecommendationImpression.user_id) & 
            (UserFeedback.product_id == RecommendationImpression.clicked_product_id),
            isouter=True
        ).filter(RecommendationImpression.shown_at >= datetime.utcnow() - timedelta(days=90)).all()
        
        if not impressions:
            logger.warning("No impression data for training")
            return None, None, None
        
        # Group by recommendation session
        groups = {}
        for imp in impressions:
            key = imp.recommendation_id
            if key not in groups:
                groups[key] = []
            groups[key].append(imp)
        
        X, y, group_sizes = [], [], []
        
        for rec_id, imps in groups.items():
            rec = Recommendation.query.get(rec_id)
            if not rec:
                continue
            
            product_ids = rec.get_product_ids()
            if not product_ids:
                continue
            
            group_features = []
            group_labels = []
            
            for imp in imps:
                for pos, pid in enumerate(imp.get_product_ids()):
                    # Get retrieval scores (simplified - would need historical)
                    retrieval_scores = {'semantic': 0.5, 'collaborative': 0.3, 'popularity': 0.2, 'content': 0.1, 'quiz': 0.0}
                    
                    user_profile = UserProfile.query.filter_by(user_id=imp.user_id).first()
                    product = Product.query.get(pid)
                    
                    feat = self.extract_features(imp.user_id, pid, retrieval_scores, user_profile, product)
                    group_features.append(feat)
                    
                    # Label: 1 if clicked, 0 otherwise (could use graded relevance)
                    label = 1.0 if imp.clicked_product_id == pid else 0.0
                    group_labels.append(label)
            
            if len(set(group_labels)) > 1:  # Need both positive and negative
                X.extend(group_features)
                y.extend(group_labels)
                group_sizes.append(len(group_features))
        
        if not X:
            return None, None, None
        
        return np.array(X), np.array(y), np.array(group_sizes)
    
    def train(self, force_retrain: bool = False) -> bool:
        """Train the LightGBM ranker."""
        model_path = self.model_dir / "ranker_model.txt"
        
        if not force_retrain and model_path.exists():
            try:
                self.model = lgb.Booster(model_file=str(model_path))
                self.is_trained = True
                logger.info("Loaded existing LightGBM ranker model")
                return True
            except Exception as e:
                logger.warning(f"Failed to load existing model: {e}")
        
        X, y, group = self.prepare_training_data()
        if X is None:
            logger.warning("Insufficient training data for ranker")
            return False
        
        logger.info(f"Training LightGBM ranker on {len(X)} samples, {len(group)} groups")
        
        # Create LightGBM dataset
        train_data = lgb.Dataset(X, label=y, group=group)
        
        params = {
            'objective': 'lambdarank',
            'metric': 'ndcg',
            'ndcg_eval_at': [1, 3, 5, 10],
            'learning_rate': 0.05,
            'num_leaves': 63,
            'max_depth': 6,
            'min_data_in_leaf': 10,
            'feature_fraction': 0.8,
            'bagging_fraction': 0.8,
            'bagging_freq': 5,
            'lambda_l1': 0.1,
            'lambda_l2': 0.1,
            'verbosity': -1,
            'random_state': 42
        }
        
        # Train with early stopping
        self.model = lgb.train(
            params,
            train_data,
            num_boost_round=200,
            valid_sets=[train_data],
            callbacks=[lgb.early_stopping(20), lgb.log_evaluation(50)]
        )
        
        # Save model
        self.model.save_model(str(model_path))
        
        # Save feature names
        self.feature_names = [f"f{i}" for i in range(X.shape[1])]
        with open(self.model_dir / "feature_names.json", "w") as f:
            json.dump(self.feature_names, f)
        
        # Save to database
        ranking_model = RankingModel(
            version=f"v{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}",
            model_path=str(model_path),
            feature_names_json=json.dumps(self.feature_names),
            training_samples=len(X),
            is_active=True,
            activated_at=datetime.utcnow()
        )
        db.session.add(ranking_model)
        db.session.commit()
        
        self.is_trained = True
        logger.info("LightGBM ranker training complete")
        return True
    
    def predict(self, features: np.ndarray) -> float:
        """Predict relevance score."""
        if not self.is_trained or self.model is None:
            return 0.5
        try:
            return float(self.model.predict(features.reshape(1, -1))[0])
        except Exception:
            return 0.5


class DiversityOptimizer:
    """
    Maximal Marginal Relevance (MMR) for diversity injection.
    Balances relevance vs diversity in final recommendation set.
    """
    
    def __init__(self, lambda_param: float = 0.7):
        self.lambda_param = lambda_param  # 0 = max diversity, 1 = max relevance
        self.embedding_cache = {}
    
    def get_product_embedding(self, product_id: int) -> Optional[np.ndarray]:
        """Get cached or compute product embedding for diversity."""
        if product_id in self.embedding_cache:
            return self.embedding_cache[product_id]
        
        # Use vector store's embedding function
        product = Product.query.get(product_id)
        if not product:
            return None
        
        doc_text = get_vector_store()._prepare_document(product.to_dict())
        embedding = np.array(get_vector_store().embedding_fn([doc_text])[0])
        self.embedding_cache[product_id] = embedding
        return embedding
    
    def mmr_rerank(
        self, 
        candidates: List[RankedRecommendation], 
        top_k: int,
        lambda_param: float = None
    ) -> List[RankedRecommendation]:
        """
        Apply MMR reranking to balance relevance and diversity.
        """
        lambda_param = lambda_param or self.lambda_param
        
        if len(candidates) <= top_k:
            return candidates
        
        selected = []
        remaining = candidates.copy()
        
        # Start with highest relevance
        remaining.sort(key=lambda x: x.final_score, reverse=True)
        selected.append(remaining.pop(0))
        
        while len(selected) < top_k and remaining:
            best_score = -1
            best_idx = -1
            
            for i, candidate in enumerate(remaining):
                # Relevance score
                relevance = candidate.final_score
                
                # Diversity: max similarity to already selected
                cand_emb = self.get_product_embedding(candidate.product_id)
                if cand_emb is not None:
                    max_sim = 0
                    for sel in selected:
                        sel_emb = self.get_product_embedding(sel.product_id)
                        if sel_emb is not None:
                            sim = np.dot(cand_emb, sel_emb) / (
                                np.linalg.norm(cand_emb) * np.linalg.norm(sel_emb) + 1e-8
                            )
                            max_sim = max(max_sim, sim)
                    diversity = 1.0 - max_sim
                else:
                    diversity = 0.5
                
                # MMR score
                mmr_score = lambda_param * relevance + (1 - lambda_param) * diversity
                
                if mmr_score > best_score:
                    best_score = mmr_score
                    best_idx = i
            
            if best_idx >= 0:
                selected.append(remaining.pop(best_idx))
            else:
                break
        
        return selected


class AdvancedRecommendationEngine:
    """
    Main orchestrator for the advanced recommendation system.
    Combines all components: hybrid retrieval, ranking, diversity, feedback.
    """
    
    def __init__(self):
        self.collaborative_engine = CollaborativeFilteringEngine()
        self.popularity_engine = PopularityEngine()
        self.ranker = LightGBMRanker()
        self.diversity_optimizer = DiversityOptimizer()
        self.last_collaborative_train = None
        self.last_popularity_update = None
    
    def initialize(self):
        """Initialize all components."""
        logger.info("Initializing Advanced Recommendation Engine")
        
        # Train collaborative filtering
        self.collaborative_engine.build_interaction_matrix()
        self.collaborative_engine.train_als()
        
        # Compute popularity
        self.popularity_engine.compute_popularity()
        
        # Train ranker
        self.ranker.train()
        
        logger.info("Advanced Recommendation Engine initialized")
    
    def get_recommendations(
        self,
        user_id: int,
        session_id: str,
        events: List[Dict],
        trigger_reason: str = "behavior_update",
        top_k: int = 5,
        experiment_variant: str = "control"
    ) -> Dict[str, Any]:
        """
        Main recommendation pipeline:
        1. Hybrid Retrieval (semantic + collaborative + popularity + content + quiz)
        2. Feature extraction
        3. LightGBM Ranking
        4. MMR Diversity Optimization
        5. Explanation generation
        """
        start_time = time.time()
        
        # Get user profile
        user_profile = UserProfile.query.filter_by(user_id=user_id).first()
        
        # ===== STAGE 1: HYBRID RETRIEVAL =====
        retrieval_results = self._hybrid_retrieval(user_id, events, user_profile, top_k * 3)
        
        if not retrieval_results:
            logger.warning(f"No retrieval results for user {user_id}")
            return self._fallback_recommendations(user_id, top_k)
        
        # ===== STAGE 2: FEATURE EXTRACTION & RANKING =====
        ranked_candidates = []
        for result in retrieval_results:
            product = Product.query.get(result.product_id)
            if not product:
                continue
            
            retrieval_scores = {
                'semantic': result.score if result.source == 'semantic' else 0.0,
                'collaborative': result.score if result.source == 'collaborative' else 0.0,
                'popularity': result.score if result.source == 'popularity' else 0.0,
                'content': result.score if result.source == 'content' else 0.0,
                'quiz': result.score if result.source == 'quiz' else 0.0
            }
            
            # Extract features
            features = self.ranker.extract_features(user_id, result.product_id, retrieval_scores, user_profile, product)
            
            # Get ranker score
            ranker_score = self.ranker.predict(features) if self.ranker.is_trained else np.mean(list(retrieval_scores.values()))
            
            # Combine scores (weighted)
            final_score = (
                0.3 * ranker_score +
                0.2 * retrieval_scores.get('semantic', 0) +
                0.2 * retrieval_scores.get('collaborative', 0) +
                0.15 * retrieval_scores.get('popularity', 0) +
                0.1 * retrieval_scores.get('content', 0) +
                0.05 * retrieval_scores.get('quiz', 0)
            )
            
            ranked = RankedRecommendation(
                product_id=result.product_id,
                final_score=final_score,
                retrieval_scores=retrieval_scores,
                ranker_score=ranker_score,
                diversity_penalty=0.0
            )
            ranked_candidates.append(ranked)
        
        # ===== STAGE 3: DIVERSITY OPTIMIZATION (MMR) =====
        if experiment_variant in ['diversity_boost', 'hybrid_rerank']:
            lambda_param = 0.5 if experiment_variant == 'diversity_boost' else 0.7
            ranked_candidates = self.diversity_optimizer.mmr_rerank(ranked_candidates, top_k, lambda_param)
        else:
            ranked_candidates.sort(key=lambda x: x.final_score, reverse=True)
            ranked_candidates = ranked_candidates[:top_k]
        
        # ===== STAGE 4: EXPLANATION GENERATION =====
        for ranked in ranked_candidates:
            ranked.explanation = self._generate_explanation(ranked, user_profile, events)
        
        # ===== STAGE 5: BUILD RESPONSE =====
        recommended_products = []
        for ranked in ranked_candidates:
            product = Product.query.get(ranked.product_id)
            if product:
                p_dict = product.to_dict()
                p_dict['recommendation_score'] = ranked.final_score
                p_dict['recommendation_explanation'] = ranked.explanation
                p_dict['retrieval_sources'] = [k for k, v in ranked.retrieval_scores.items() if v > 0]
                recommended_products.append(p_dict)
        
        # Generate narrative using LLM
        narrative = self._generate_narrative(user_id, recommended_products, events, user_profile)
        
        # Log impression
        self._log_impression(user_id, recommended_products, experiment_variant, session_id)
        
        total_time = (time.time() - start_time) * 1000
        logger.info(f"Recommendation generated for user {user_id} in {total_time:.1f}ms, variant={experiment_variant}")
        
        return {
            'narrative': narrative,
            'recommended_product_ids': [p['id'] for p in recommended_products],
            'recommended_products': recommended_products,
            'trigger_reason': trigger_reason,
            'metadata': {
                'variant': experiment_variant,
                'retrieval_count': len(retrieval_results),
                'ranked_count': len(ranked_candidates),
                'generation_time_ms': total_time
            }
        }
    
    def _hybrid_retrieval(
        self,
        user_id: int,
        events: List[Dict],
        user_profile: Optional[UserProfile],
        top_k: int
    ) -> List[RetrievalResult]:
        """Multi-source retrieval with score fusion."""
        results = []
        
        # 1. Semantic search (vector store)
        if events:
            intent_text = self._build_intent_query(events, user_profile)
            semantic_results = get_vector_store().semantic_search(intent_text, top_k=top_k)
            for r in semantic_results:
                results.append(RetrievalResult(
                    product_id=r['product_id'],
                    score=r.get('similarity_score', 0.8),
                    source='semantic',
                    metadata=r.get('metadata', {})
                ))
        
        # 2. Collaborative filtering
        cf_results = self.collaborative_engine.get_user_recommendations(user_id, top_k=top_k)
        for pid, score in cf_results:
            results.append(RetrievalResult(
                product_id=pid,
                score=min(score, 1.0),
                source='collaborative'
            ))
        
        # 3. Popularity-based
        cat = self._get_top_category(events, user_profile)
        pop_results = self.popularity_engine.get_top_popular(top_k=top_k, category=cat)
        for pid, score in pop_results:
            results.append(RetrievalResult(
                product_id=pid,
                score=score,
                source='popularity'
            ))
        
        # 4. Content-based (category/tag matching)
        if events:
            content_results = self._content_based_retrieval(events, top_k)
            for pid, score in content_results:
                results.append(RetrievalResult(
                    product_id=pid,
                    score=score,
                    source='content'
                ))
        
        # 5. Quiz-based (onboarding preferences)
        if user_profile and user_profile.get_quiz_responses():
            quiz_results = self._quiz_based_retrieval(user_profile, top_k)
            for pid, score in quiz_results:
                results.append(RetrievalResult(
                    product_id=pid,
                    score=score,
                    source='quiz'
                ))
        
        # Fuse results using reciprocal rank fusion
        return self._fuse_retrieval_results(results, top_k)
    
    def _build_intent_query(self, events: List[Dict], user_profile: Optional[UserProfile]) -> str:
        """Build semantic search query from user behavior."""
        parts = []
        
        if user_profile:
            goals = user_profile.get_learning_goals()
            parts.extend(goals[:3])
            cat_affinity = user_profile.get_category_affinity()
            if cat_affinity:
                top_cat = max(cat_affinity, key=cat_affinity.get)
                parts.append(top_cat)
        
        searches = [e.get('details', {}).get('query', '') for e in events if e.get('event_type') == 'search']
        parts.extend(searches[-3:])
        
        return " ".join(filter(None, parts)) or "software engineering courses"
    
    def _get_top_category(self, events: List[Dict], user_profile: Optional[UserProfile]) -> Optional[str]:
        """Determine user's top interest category."""
        if user_profile:
            cat_affinity = user_profile.get_category_affinity()
            if cat_affinity:
                return max(cat_affinity, key=cat_affinity.get)
        
        # From recent events
        cat_weights = {}
        for e in events:
            details = e.get('details', {})
            cat = details.get('category')
            if cat:
                cat_weights[cat] = cat_weights.get(cat, 0) + 1
        
        return max(cat_weights, key=cat_weights.get) if cat_weights else None
    
    def _content_based_retrieval(self, events: List[Dict], top_k: int) -> List[Tuple[int, float]]:
        """TF-IDF based content similarity."""
        # Build user profile text
        user_text = " ".join([
            e.get('details', {}).get('query', '') 
            for e in events if e.get('event_type') == 'search'
        ])
        
        if not user_text:
            return []
        
        # Get all products
        products = Product.query.all()
        if not products:
            return []
        
        # TF-IDF vectorization
        corpus = [user_text] + [f"{p.title} {p.description} {p.tags or ''}" for p in products]
        
        vectorizer = TfidfVectorizer(max_features=5000, stop_words='english', ngram_range=(1, 2))
        tfidf_matrix = vectorizer.fit_transform(corpus)
        
        # Cosine similarity
        user_vec = tfidf_matrix[0:1]
        product_vecs = tfidf_matrix[1:]
        similarities = cosine_similarity(user_vec, product_vecs).flatten()
        
        # Top-k
        top_indices = np.argsort(similarities)[::-1][:top_k]
        return [(products[i].id, float(similarities[i])) for i in top_indices if similarities[i] > 0.1]
    
    def _quiz_based_retrieval(self, user_profile: UserProfile, top_k: int) -> List[Tuple[int, float]]:
        """Retrieve based on onboarding quiz responses."""
        quiz = user_profile.get_quiz_responses()
        interest_areas = quiz.get('interest_areas', [])
        goals = quiz.get('goals', [])
        
        if not interest_areas:
            return []
        
        # Search products matching interest areas
        results = []
        for area in interest_areas:
            matching = Product.query.filter(
                db.or_(
                    Product.category.ilike(f"%{area}%"),
                    Product.tags.ilike(f"%{area}%"),
                    Product.description.ilike(f"%{area}%")
                )
            ).limit(top_k).all()
            
            for p in matching:
                results.append((p.id, 0.8))
        
        return results[:top_k]
    
    def _fuse_retrieval_results(self, results: List[RetrievalResult], top_k: int) -> List[RetrievalResult]:
        """Reciprocal rank fusion of multi-source results."""
        scores = {}
        sources = {}
        
        for rank, result in enumerate(results):
            pid = result.product_id
            rrf_score = 1.0 / (60 + rank + 1)  # k=60
            scores[pid] = scores.get(pid, 0) + rrf_score * result.score
            sources[pid] = sources.get(pid, []) + [result.source]
        
        # Sort by fused score
        sorted_pids = sorted(scores.keys(), key=lambda x: scores[x], reverse=True)
        
        fused = []
        for pid in sorted_pids[:top_k]:
            fused.append(RetrievalResult(
                product_id=pid,
                score=scores[pid],
                source='fused',
                metadata={'sources': sources[pid]}
            ))
        
        return fused
    
    def _generate_explanation(
        self, 
        ranked: RankedRecommendation, 
        user_profile: Optional[UserProfile],
        events: List[Dict]
    ) -> str:
        """Generate human-readable explanation for recommendation."""
        product = Product.query.get(ranked.product_id)
        if not product:
            return "Recommended based on your interests."
        
        reasons = []
        
        # Top retrieval source
        top_source = max(ranked.retrieval_scores.items(), key=lambda x: x[1])[0]
        source_explanations = {
            'semantic': "matches your recent searches and interests",
            'collaborative': "learners with similar interests enjoyed this",
            'popularity': "trending among learners in your domain",
            'content': "covers topics you've been exploring",
            'quiz': "aligns with your stated learning goals"
        }
        
        if top_source in source_explanations:
            reasons.append(source_explanations[top_source])
        
        # Category match
        if user_profile:
            cat_affinity = user_profile.get_category_affinity()
            if product.category in cat_affinity:
                reasons.append(f"strong match for your {product.category} focus")
        
        # Skill level match
        if user_profile and user_profile.skill_level != 'beginner':
            reasons.append(f"suitable for {user_profile.skill_level} learners")
        
        return "; ".join(reasons[:2]) + "."
    
    def _generate_narrative(
        self,
        user_id: int,
        products: List[Dict],
        events: List[Dict],
        user_profile: Optional[UserProfile]
    ) -> str:
        """Generate personalized narrative using LLM (fallback to template)."""
        user = User.query.get(user_id)
        user_name = user.name if user else "Learner"
        
        top_categories = list(set(p['category'] for p in products[:3]))
        
        template = (
            f"Hey {user_name}! Based on your recent activity exploring "
            f"{', '.join(top_categories)}, I've curated these masterclasses "
            f"that perfectly align with your learning trajectory. "
            f"Each recommendation is ranked by our AI to maximize your skill growth. "
            f"Dive in and accelerate your journey!"
        )
        
        return template
    
    def _fallback_recommendations(self, user_id: int, top_k: int) -> Dict[str, Any]:
        """Fallback when no retrieval results."""
        popular = self.popularity_engine.get_top_popular(top_k)
        products = []
        for pid, score in popular:
            p = Product.query.get(pid)
            if p:
                p_dict = p.to_dict()
                p_dict['recommendation_score'] = score
                p_dict['recommendation_explanation'] = "Popular among all learners"
                products.append(p_dict)
        
        return {
            'narrative': "Here are the most popular masterclasses to get you started!",
            'recommended_product_ids': [p['id'] for p in products],
            'recommended_products': products,
            'trigger_reason': 'fallback',
            'metadata': {'variant': 'fallback'}
        }
    
    def _log_impression(
        self,
        user_id: int,
        products: List[Dict],
        variant: str,
        session_id: str
    ):
        """Log recommendation impression for learning."""
        try:
            impression = RecommendationImpression(
                user_id=user_id,
                product_ids_json=json.dumps([p['id'] for p in products]),
                positions_json=json.dumps(list(range(len(products)))),
                experiment_variant=variant
            )
            db.session.add(impression)
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            logger.warning(f"Failed to log impression: {e}")
    
    def record_feedback(
        self,
        user_id: int,
        product_id: int,
        feedback_type: str,
        value: float = 1.0,
        context: Dict = None,
        session_id: str = None,
        recommendation_id: int = None
    ):
        """Record user feedback for online learning."""
        try:
            feedback = UserFeedback(
                user_id=user_id,
                product_id=product_id,
                feedback_type=feedback_type,
                value=value,
                context_json=json.dumps(context or {}),
                session_id=session_id,
                recommendation_id=recommendation_id
            )
            db.session.add(feedback)
            
            # Update user profile incrementally
            self._update_user_profile_incremental(user_id, product_id, feedback_type, value)
            
            db.session.commit()
            
            # Trigger async model update (could use Celery)
            logger.info(f"Feedback recorded: user={user_id}, product={product_id}, type={feedback_type}")
        except Exception as e:
            db.session.rollback()
            logger.error(f"Failed to record feedback: {e}")
    
    def _update_user_profile_incremental(
        self,
        user_id: int,
        product_id: int,
        feedback_type: str,
        value: float
    ):
        """Update user profile affinities incrementally."""
        profile = UserProfile.query.filter_by(user_id=user_id).first()
        if not profile:
            profile = UserProfile(user_id=user_id)
            db.session.add(profile)
        
        product = Product.query.get(product_id)
        if not product:
            return
        
        # Update category affinity
        cat_affinity = profile.get_category_affinity()
        cat = product.category
        
        if feedback_type in ['explicit_like', 'implicit_enroll', 'implicit_click']:
            weight = 0.1 if 'implicit' in feedback_type else 0.2
        elif feedback_type in ['explicit_dislike', 'explicit_not_relevant']:
            weight = -0.15
        else:
            weight = 0.05
        
        cat_affinity[cat] = cat_affinity.get(cat, 0) + weight
        # Decay old affinities
        cat_affinity = {k: v * 0.99 for k, v in cat_affinity.items() if v > 0.01}
        profile.category_affinity_json = json.dumps(cat_affinity)
        
        # Update topic affinity from tags
        topic_affinity = profile.get_topic_affinity()
        if product.tags:
            for tag in product.tags:
                topic_affinity[tag] = topic_affinity.get(tag, 0) + weight * 0.5
        topic_affinity = {k: v * 0.99 for k, v in topic_affinity.items() if v > 0.01}
        profile.topic_affinity_json = json.dumps(topic_affinity)
        
        # Update engagement metrics
        profile.total_events += 1
        if feedback_type == 'implicit_click':
            profile.total_clicks += 1
        if feedback_type == 'implicit_enroll':
            profile.total_enrollments += 1
        
        if profile.total_recommendations_shown > 0:
            profile.ctr = profile.total_clicks / profile.total_recommendations_shown
        
        profile.updated_at = datetime.utcnow()
    
    def get_ab_variant(self, user_id: int, experiment_name: str = "recommendation_algorithm") -> str:
        """Get or assign A/B test variant for user."""
        assignment = ABTestAssignment.query.filter_by(
            user_id=user_id, experiment_name=experiment_name
        ).first()
        
        if assignment:
            return assignment.variant
        
        # Assign variant (deterministic hash-based)
        variants = ['control', 'hybrid_rerank', 'collaborative', 'diversity_boost']
        variant_idx = hash(f"{user_id}_{experiment_name}") % len(variants)
        variant = variants[variant_idx]
        
        assignment = ABTestAssignment(
            user_id=user_id,
            experiment_name=experiment_name,
            variant=variant
        )
        db.session.add(assignment)
        db.session.commit()
        
        return variant


# Global instance
advanced_recommender = AdvancedRecommendationEngine()