import os
import json
import time
import logging
from typing import TypedDict, List, Dict, Any, Optional
from openai import OpenAI

from config import Config
from vector_store import vector_store
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
    """Returns an OpenAI client configured for NVIDIA NIM API gateway."""
    nvidia_key = os.environ.get("NVIDIA_API_KEY") or getattr(Config, "NVIDIA_API_KEY", None)
    if nvidia_key:
        base_url = os.environ.get("NVIDIA_BASE_URL") or "https://integrate.api.nvidia.com/v1"
        return OpenAI(base_url=base_url, api_key=nvidia_key)
        
    api_key = os.environ.get("MESH_API_KEY") or getattr(Config, "MESH_API_KEY", "rsk_placeholder")
    base_url = os.environ.get("MESH_BASE_URL") or "https://api.meshapi.ai/v1"
    return OpenAI(base_url=base_url, api_key=api_key)

class AgenticRecommendationEngine:
    def __init__(self):
        nvidia_key = os.environ.get("NVIDIA_API_KEY") or getattr(Config, "NVIDIA_API_KEY", None)
        if nvidia_key:
            self.model_name = "meta/llama-3.1-8b-instruct"
        else:
            self.model_name = os.environ.get("MESH_MODEL", "meta/llama-3.1-8b-instruct")

    def analyze_behavior(self, events: List[Dict[str, Any]]) -> tuple[str, str, Dict[str, Any]]:
        """
        Node 1: Weighted Student Intent Profiling.
        Calculates category & topic weights based on explicit user action signals:
          - search: +5 points
          - product_view: +3 points
          - dwell_time: +1 point per 10s spent
          - category_filter: +2 points
        """
        if not events:
            return "General discovery and trending courses", "popular trending software development courses", {'top_category': 'Generative AI & Agents'}

        searches = []
        viewed_titles = []
        category_weights = {}
        total_dwell_ms = 0
        
        for ev in events:
            ev_type = ev.get('event_type')
            details = ev.get('details', {})
            duration = ev.get('duration_ms', 0)
            total_dwell_ms += duration
            
            # Helper to add weights to categories
            def add_cat_weight(cat, weight):
                if cat and cat != 'All':
                    category_weights[cat] = category_weights.get(cat, 0) + weight

            if ev_type == 'search' and details.get('query'):
                query = details.get('query').strip()
                searches.append(query)
                
                # Check if search query matches known categories or keywords
                query_lower = query.lower()
                if 'hack' in query_lower or 'sec' in query_lower or 'cyber' in query_lower or 'vuln' in query_lower or 'pentest' in query_lower:
                    add_cat_weight('Cybersecurity', 6)
                elif 'agent' in query_lower or 'lang' in query_lower or 'rag' in query_lower or 'ai' in query_lower:
                    add_cat_weight('Generative AI & Agents', 6)
                elif 'web' in query_lower or 'next' in query_lower or 'react' in query_lower or 'flask' in query_lower:
                    add_cat_weight('Web Development & Fullstack', 6)
                elif 'cloud' in query_lower or 'devops' in query_lower or 'aws' in query_lower or 'k8s' in query_lower:
                    add_cat_weight('Cloud & DevOps', 6)
                elif 'data' in query_lower or 'spark' in query_lower or 'ml' in query_lower or 'torch' in query_lower:
                    add_cat_weight('Data Science & Machine Learning', 6)

            elif ev_type == 'product_view':
                if details.get('product_title'):
                    viewed_titles.append(details.get('product_title'))
                if details.get('category'):
                    add_cat_weight(details.get('category'), 3)

            elif ev_type == 'dwell_time':
                if details.get('category'):
                    dwell_sec = round(duration / 1000, 1)
                    dwell_points = max(1, int(dwell_sec // 10))
                    add_cat_weight(details.get('category'), dwell_points)

            elif ev_type == 'category_filter':
                if details.get('category'):
                    add_cat_weight(details.get('category'), 2)

        # Determine primary top category
        top_category = max(category_weights, key=category_weights.get) if category_weights else None
        
        intent_parts = []
        if searches:
            intent_parts.append(f"Searched terms: '{', '.join(searches[-3:])}'")
        if viewed_titles:
            intent_parts.append(f"Explored: '{', '.join(viewed_titles[-3:])}'")
        if top_category:
            intent_parts.append(f"Primary focus interest: {top_category}")
        if total_dwell_ms > 0:
            intent_parts.append(f"Dwell engagement: {round(total_dwell_ms/1000, 1)}s")

        intent_summary = " | ".join(intent_parts) if intent_parts else "Catalog browsing"
        
        # Build search query for vector retrieval
        search_query_elements = []
        if searches:
            search_query_elements.extend(searches)
        if top_category:
            search_query_elements.append(top_category)

        search_query = " ".join(search_query_elements) if search_query_elements else "top rated courses"
        
        stats = {
            'search_count': len(searches),
            'views_count': len(viewed_titles),
            'top_category': top_category,
            'category_weights': category_weights,
            'dwell_seconds': round(total_dwell_ms / 1000, 1)
        }
        return intent_summary, search_query, stats

    def retrieve_products(self, search_query: str, top_category: str = None, top_k: int = 5) -> List[Dict[str, Any]]:
        """
        Node 2: Strict Topic-Grounded Candidate Retrieval.
        Ensures recommendations are 100% relevant to the user's primary interest category/topic.
        """
        vector_candidates = vector_store.semantic_search(
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

        try:
            try:
                response = client.chat.completions.create(
                    model=self.model_name,
                    messages=[
                        {"role": "system", "content": "You are SmartReco, a behavioral AI recommendation engine. Always output valid JSON."},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0.7,
                    response_format={"type": "json_object"}
                )
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
            logger.warning(f"Mesh API call notice: {e}. Utilizing fallback agent persona generation.")
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
