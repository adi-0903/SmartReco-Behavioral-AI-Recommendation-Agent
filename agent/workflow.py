import os
import json
import time
import logging
from typing import TypedDict, List, Dict, Any, Optional
from openai import OpenAI

from config import Config
from vector_store import get_vector_store
from models import Product, db
from agent.observability import AgentTrace

logger = logging.getLogger(__name__)

class RecommendationState(TypedDict):
    user_id: int
    session_id: str
    events: List[Dict[str, Any]]
    intent_summary: str
    search_query: str
    candidates: List[Dict[str, Any]]
    retrieval_quality: Dict[str, Any]
    llm_prompt: str
    narrative: str
    recommended_product_ids: List[int]
    trigger_reason: str
    trace_id: str

def get_llm_client():
    """Returns an OpenAI client configured for Mesh API gateway or NVIDIA NIM API fallback."""
    mesh_key = os.environ.get("MESH_API_KEY") or getattr(Config, "MESH_API_KEY", "")
    if mesh_key and mesh_key.startswith("rsk_") and len(mesh_key) > 10:
        base_url = os.environ.get("MESH_BASE_URL") or "https://api.meshapi.ai/v1"
        return OpenAI(base_url=base_url, api_key=mesh_key)

    nvidia_key = os.environ.get("NVIDIA_API_KEY") or getattr(Config, "NVIDIA_API_KEY", None)
    if nvidia_key:
        base_url = os.environ.get("NVIDIA_BASE_URL") or "https://integrate.api.nvidia.com/v1"
        return OpenAI(base_url=base_url, api_key=nvidia_key)

    base_url = os.environ.get("MESH_BASE_URL") or "https://api.meshapi.ai/v1"
    return OpenAI(base_url=base_url, api_key=mesh_key or "rsk_placeholder")


def supports_json_mode(model_name: str) -> bool:
    """Check if model supports JSON response format."""
    json_supported_models = [
        "gpt-4", "gpt-4o", "gpt-4-turbo", "gpt-3.5-turbo",
        "openai/gpt-4o", "openai/gpt-4-turbo", "openai/gpt-3.5-turbo",
    ]
    model_lower = model_name.lower()
    return any(supported in model_lower for supported in json_supported_models)


class AgenticRecommendationEngine:
    def __init__(self):
        mesh_key = os.environ.get("MESH_API_KEY") or getattr(Config, "MESH_API_KEY", "")
        if mesh_key and mesh_key.startswith("rsk_") and len(mesh_key) > 10:
            self.model_name = os.environ.get("MESH_MODEL") or getattr(Config, "MESH_MODEL", "openai/gpt-4o")
        else:
            self.model_name = os.environ.get("NVIDIA_MODEL") or getattr(Config, "NVIDIA_MODEL", "meta/llama-3.1-8b-instruct")

    def analyze_behavior(self, events: List[Dict[str, Any]]) -> tuple[str, str, Dict[str, Any]]:
        """
        Node 1: Weighted Student Intent Profiling with Recency Decay.
        Calculates category & topic weights based on explicit user action signals:
          - search: +5 points (recent searches weighted higher)
          - product_view: +3 points
          - dwell_time: +1 point per 10s spent
          - category_filter: +2 points
          - click_recommendation: +4 points (strong intent signal)
          - enroll_click: +5 points (strongest intent)
        Applies exponential time decay (half-life: 24 hours) to older events.
        """
        if not events:
            return "General discovery and trending courses", "popular trending software development courses", {'top_category': 'Generative AI & Agents'}

        from datetime import datetime, timedelta
        now = datetime.utcnow()
        half_life_hours = 24
        
        searches = []
        viewed_titles = []
        category_weights = {}
        topic_weights = {}
        total_dwell_ms = 0
        event_recency_scores = []
        
        for ev in events:
            ev_type = ev.get('event_type')
            details = ev.get('details', {})
            duration = ev.get('duration_ms', 0)
            total_dwell_ms += duration
            
            # Calculate recency decay factor
            ev_timestamp = ev.get('timestamp')
            if ev_timestamp:
                try:
                    if isinstance(ev_timestamp, str):
                        ev_time = datetime.fromisoformat(ev_timestamp.replace('Z', '+00:00'))
                    else:
                        ev_time = ev_timestamp
                    hours_ago = (now - ev_time).total_seconds() / 3600
                    decay_factor = 2 ** (-hours_ago / half_life_hours)
                except Exception:
                    decay_factor = 0.5
            else:
                decay_factor = 0.5
            
            event_recency_scores.append(decay_factor)
            
            # Helper to add weights to categories with recency decay
            def add_cat_weight(cat, base_weight):
                if cat and cat != 'All':
                    weighted = base_weight * decay_factor
                    category_weights[cat] = category_weights.get(cat, 0) + weighted
            
            # Helper to add topic weights from search queries
            def add_topic_weight(topic, base_weight):
                if topic:
                    weighted = base_weight * decay_factor
                    topic_weights[topic] = topic_weights.get(topic, 0) + weighted

            if ev_type == 'search' and details.get('query'):
                query = details.get('query').strip()
                searches.append(query)
                
                # Enhanced keyword-based category detection
                query_lower = query.lower()
                keywords = query_lower.split()
                
                # Category detection with keyword scoring
                cat_scores = {
                    'Cybersecurity': ['hack', 'sec', 'cyber', 'vuln', 'pentest', 'exploit', 'malware', 'phish', 'ransom', 'soc', 'threat', 'bug bounty', 'owasp'],
                    'Generative AI & Agents': ['agent', 'lang', 'rag', 'ai', 'llm', 'gpt', 'claude', 'gemini', 'prompt', 'fine-tun', 'lora', 'qlora', 'vector', 'embedding', 'multimodal', 'vlm'],
                    'Web Development & Fullstack': ['web', 'next', 'react', 'flask', 'fastapi', 'django', 'vue', 'angular', 'typescript', 'tailwind', 'css', 'html', 'frontend', 'backend', 'api', 'graphql', 'rest'],
                    'Cloud & DevOps': ['cloud', 'devops', 'aws', 'k8s', 'kubernetes', 'docker', 'terraform', 'ansible', 'ci/cd', 'jenkins', 'github action', 'gitlab', 'helm', 'argo', 'prometheus', 'grafana', 'sre', 'observability'],
                    'Data Science & Machine Learning': ['data', 'spark', 'ml', 'torch', 'tensor', 'pytorch', 'tensorflow', 'sklearn', 'xgboost', 'pandas', 'numpy', 'mlops', 'feature', 'drift', 'forecast', 'time series', 'nlp', 'bert', 'transformer'],
                }
                
                for cat, kw_list in cat_scores.items():
                    score = sum(1 for kw in kw_list if kw in query_lower)
                    if score > 0:
                        add_cat_weight(cat, 5 * score)
                
                # Track individual topics
                for kw in keywords:
                    if len(kw) > 3:
                        add_topic_weight(kw, 2)

            elif ev_type == 'product_view':
                if details.get('product_title'):
                    viewed_titles.append(details.get('product_title'))
                if details.get('category'):
                    add_cat_weight(details.get('category'), 3)
                
                # Extract topics from product title
                title = details.get('product_title', '').lower()
                for kw in title.split():
                    if len(kw) > 4:
                        add_topic_weight(kw, 1)

            elif ev_type == 'dwell_time':
                if details.get('category'):
                    dwell_sec = round(duration / 1000, 1)
                    dwell_points = max(1, int(dwell_sec // 10))
                    add_cat_weight(details.get('category'), dwell_points)

            elif ev_type == 'category_filter':
                if details.get('category'):
                    add_cat_weight(details.get('category'), 2)

            elif ev_type == 'click_recommendation':
                if details.get('category'):
                    add_cat_weight(details.get('category'), 4)
                if details.get('product_title'):
                    add_topic_weight(details.get('product_title', '').lower().split()[0] if details.get('product_title') else '', 3)

            elif ev_type == 'enroll_click':
                if details.get('category'):
                    add_cat_weight(details.get('category'), 5)
                if details.get('product_title'):
                    add_topic_weight(details.get('product_title', '').lower().split()[0] if details.get('product_title') else '', 4)

        # Determine primary top category
        top_category = max(category_weights, key=category_weights.get) if category_weights else None
        top_topic = max(topic_weights, key=topic_weights.get) if topic_weights else None
        
        intent_parts = []
        if searches:
            intent_parts.append(f"Searched terms: '{', '.join(searches[-3:])}'")
        if viewed_titles:
            intent_parts.append(f"Explored: '{', '.join(viewed_titles[-3:])}'")
        if top_category:
            intent_parts.append(f"Primary focus interest: {top_category}")
        if top_topic:
            intent_parts.append(f"Key topic: {top_topic}")
        if total_dwell_ms > 0:
            intent_parts.append(f"Dwell engagement: {round(total_dwell_ms/1000, 1)}s")
        
        # Calculate engagement level
        avg_recency = sum(event_recency_scores) / len(event_recency_scores) if event_recency_scores else 0
        engagement_level = "high" if avg_recency > 0.5 else "medium" if avg_recency > 0.2 else "low"
        
        intent_summary = " | ".join(intent_parts) if intent_parts else "Catalog browsing"
        
        # Build search query for vector retrieval
        search_query_elements = []
        if searches:
            search_query_elements.extend(searches[-3:])  # Recent searches weighted more
        if top_category:
            search_query_elements.append(top_category)
        if top_topic:
            search_query_elements.append(top_topic)

        search_query = " ".join(search_query_elements) if search_query_elements else "top rated courses"
        
        stats = {
            'search_count': len(searches),
            'views_count': len(viewed_titles),
            'top_category': top_category,
            'top_topic': top_topic,
            'category_weights': {k: round(v, 2) for k, v in category_weights.items()},
            'topic_weights': {k: round(v, 2) for k, v in topic_weights.items()},
            'dwell_seconds': round(total_dwell_ms / 1000, 1),
            'engagement_level': engagement_level,
            'avg_recency_score': round(avg_recency, 3),
            'total_events': len(events)
        }
        return intent_summary, search_query, stats

    def retrieve_products(self, search_query: str, top_category: str = None, top_k: int = 5) -> List[Dict[str, Any]]:
        """
        Node 2: Strict Topic-Grounded Candidate Retrieval.
        Ensures recommendations are 100% relevant to the user's primary interest category/topic.
        """
        vector_candidates = get_vector_store().semantic_search(
            query_text=search_query,
            top_k=top_k,
            category_filter=top_category if (top_category and top_category != "All") else None
        )
        
        candidates = []
        retrieved_ids = set()
        
        for vc in vector_candidates:
            p_id = vc['product_id']
            retrieved_ids.add(p_id)
            product = Product.query.get(p_id)
            if product:
                prod_dict = product.to_dict()
                prod_dict['similarity_score'] = vc.get('similarity_score', 0.85)
                candidates.append(prod_dict)

        # 1. Fallback: Search SQL DB for products matching top_category
        if len(candidates) < top_k and top_category and top_category != "All":
            cat_products = Product.query.filter(
                Product.category == top_category,
                Product.id.notin_(list(retrieved_ids))
            ).all()
            
            for p in cat_products:
                retrieved_ids.add(p.id)
                prod_dict = p.to_dict()
                prod_dict['similarity_score'] = 0.75
                candidates.append(prod_dict)
                if len(candidates) >= top_k:
                    break

        # 2. Fallback: Search SQL DB for products matching search terms/keywords
        if len(candidates) < top_k and search_query:
            query_words = [w for w in search_query.split() if len(w) > 2]
            for kw in query_words:
                if len(candidates) >= top_k:
                    break
                kw_matches = Product.query.filter(
                    (Product.title.like(f"%{kw}%")) | (Product.tags.like(f"%{kw}%")),
                    Product.id.notin_(list(retrieved_ids))
                ).all()
                for p in kw_matches:
                    retrieved_ids.add(p.id)
                    prod_dict = p.to_dict()
                    prod_dict['similarity_score'] = 0.65
                    candidates.append(prod_dict)
                    if len(candidates) >= top_k:
                        break

        # STRICT TOPIC ENFORCEMENT:
        # If student has strong top_category interest and we retrieved category matches,
        # filter out any unrelated category items so recommendations are 100% focused!
        if top_category and top_category != "All":
            category_candidates = [c for c in candidates if c.get('category') == top_category]
            if len(category_candidates) >= 2:
                candidates = category_candidates

        return candidates[:top_k]

    def evaluate_retrieval(self, candidates: List[Dict[str, Any]], search_query: str) -> Dict[str, Any]:
        """
        Node 3: Evaluates candidate relevance score & coverage.
        """
        if not candidates:
            return {'status': 'insufficient', 'avg_score': 0.0, 'needs_refinement': True}
            
        avg_score = sum(c.get('similarity_score', 0.5) for c in candidates) / len(candidates)
        needs_refinement = avg_score < 0.35 or len(candidates) < 2
        
        return {
            'status': 'good' if not needs_refinement else 'marginal',
            'avg_score': round(avg_score, 4),
            'needs_refinement': needs_refinement,
            'candidate_count': len(candidates)
        }

    def generate_persuasive_narrative(
        self,
        intent_summary: str,
        user_name: str,
        candidates: List[Dict[str, Any]],
        stats: Dict[str, Any]
    ) -> tuple[str, List[int], str]:
        """
        Node 4: Uses Mesh API LLM to author dynamic personalized recommendation copy.
        Focused strictly on the student's highest-scored interest topic.
        """
        candidate_summary = "\n".join([
            f"- [{c['id']}] {c['title']} (${c['price']}) - Category: {c['category']}. Tags: {', '.join(c.get('tags', []))}. Rating: {c['rating']}/5"
            for c in candidates
        ])

        top_cat = stats.get('top_category', 'Software Engineering')

        prompt = f"""You are SmartReco, an intelligent agentic learning guide.
User Name: {user_name}
Target Primary Interest Category: {top_cat}
User Behavioral Activity Summary: {intent_summary}
User Engagement Stats: {json.dumps(stats)}

Available Relevant Courses retrieved strictly matching target domain:
{candidate_summary}

Instructions:
1. Write a captivating, highly personalized 2-paragraph narrative addressing {user_name} directly.
2. Focus strictly on their primary interest area ({top_cat}) and search terms. Explain WHY these courses match their exact recent activity.
3. Be persuasive, motivational, and highlight actionable career/skill outcomes.
4. Select the top 2 to 3 candidate course IDs from the list above.

Output strictly as a valid JSON object matching this structure:
{{
  "narrative": "Your persuasive personalized narrative here...",
  "recommended_course_ids": [id1, id2]
}}"""

        client = get_llm_client()
        narrative = ""
        recommended_ids = [c['id'] for c in candidates[:3]]
        use_json_mode = supports_json_mode(self.model_name)

        try:
            try:
                kwargs = {
                    "model": self.model_name,
                    "messages": [
                        {"role": "system", "content": "You are SmartReco, a behavioral AI recommendation engine. Always output valid JSON."},
                        {"role": "user", "content": prompt}
                    ],
                    "temperature": 0.7,
                }
                if use_json_mode:
                    kwargs["response_format"] = {"type": "json_object"}
                
                response = client.chat.completions.create(**kwargs)
            except Exception as ex1:
                logger.info(f"Retrying LLM call without response_format flag: {ex1}")
                response = client.chat.completions.create(
                    model=self.model_name,
                    messages=[
                        {"role": "user", "content": prompt}
                    ]
                )
            
            content = response.choices[0].message.content
            import re
            json_match = re.search(r'\{.*\}', content, re.DOTALL)
            if json_match:
                content = json_match.group(0)
                
            parsed = json.loads(content)
            narrative = parsed.get("narrative", "")
            rec_ids = parsed.get("recommended_course_ids", [])
            if rec_ids and isinstance(rec_ids, list):
                valid_ids = [cid for cid in rec_ids if any(c['id'] == cid for c in candidates)]
                if valid_ids:
                    recommended_ids = valid_ids
                    
        except Exception as e:
            logger.warning(f"LLM call failed: {e}. Utilizing fallback agent persona generation.")
            top_titles = [c['title'] for c in candidates[:2]]
            title_str = " and ".join(top_titles) if top_titles else f"our featured {top_cat} masterclasses"
            
            narrative = (
                f"Hey {user_name}! Based on your recent focus exploring **{top_cat}** "
                f"and active research across our interactive platform, we've curated a custom learning path just for you. "
                f"You spent significant time analyzing advanced topics, and **{title_str}** "
                f"directly align with your immediate goals to build production-grade expertise!"
            )

        return narrative, recommended_ids, prompt

    def run(self, user_id: int, session_id: str, events: List[Dict[str, Any]], trigger_reason: str = "behavior_update") -> Dict[str, Any]:
        """
        Executes the end-to-end Agentic Recommendation Workflow with Observability Tracing.
        """
        trace = AgentTrace(user_id=user_id, session_id=session_id, trigger_reason=trigger_reason)
        user_name = "Learner"
        
        from models import User
        user = User.query.get(user_id) if user_id else None
        if user:
            user_name = user.name

        try:
            # Node 1: Analyze Behavior with weighted scoring
            t0 = time.time()
            intent_summary, search_query, stats = self.analyze_behavior(events)
            trace.intent_summary = intent_summary
            trace.add_node_execution("analyze_behavior", {'events_count': len(events)}, {'intent_summary': intent_summary, 'search_query': search_query, 'top_category': stats.get('top_category')}, (time.time()-t0)*1000)

            # Node 2: Retrieve Products (Strict Topic-Grounded)
            t0 = time.time()
            candidates = self.retrieve_products(search_query, top_category=stats.get('top_category'))
            trace.retrieved_candidates = [{'id': c['id'], 'title': c['title'], 'score': c.get('similarity_score'), 'category': c.get('category')} for c in candidates]
            trace.add_node_execution("retrieve_products", {'search_query': search_query, 'top_category': stats.get('top_category')}, {'candidate_count': len(candidates)}, (time.time()-t0)*1000)

            # Node 3: Evaluate Retrieval
            t0 = time.time()
            retrieval_eval = self.evaluate_retrieval(candidates, search_query)
            if retrieval_eval['needs_refinement']:
                expanded_query = f"{search_query} {stats.get('top_category', '')} course masterclass"
                candidates = self.retrieve_products(expanded_query, top_category=stats.get('top_category'))
            trace.add_node_execution("evaluate_retrieval", retrieval_eval, {'final_candidate_count': len(candidates)}, (time.time()-t0)*1000)

            # Node 4: Generate Persuasion
            t0 = time.time()
            narrative, recommended_ids, prompt = self.generate_persuasive_narrative(
                intent_summary, user_name, candidates, stats
            )
            trace.llm_prompt = prompt
            trace.add_node_execution("generate_persuasion", {'prompt_length': len(prompt)}, {'narrative_length': len(narrative), 'rec_ids': recommended_ids}, (time.time()-t0)*1000)

            # Node 5: Finalize & Persist
            trace.finish(narrative, recommended_ids, status="completed")

            return {
                'narrative': narrative,
                'recommended_product_ids': recommended_ids,
                'recommended_products': [c for c in candidates if c['id'] in recommended_ids],
                'trigger_reason': trigger_reason,
                'trace_id': trace.trace_id,
                'metadata': {
                    'intent_summary': intent_summary,
                    'search_query': search_query,
                    'retrieval_eval': retrieval_eval,
                    'top_category': stats.get('top_category')
                }
            }

        except Exception as e:
            logger.error(f"Agent Workflow failed: {e}", exc_info=True)
            trace.finish("", [], status="failed", error=str(e))
            raise e

# Global Engine instance
recommendation_engine = AgenticRecommendationEngine()
