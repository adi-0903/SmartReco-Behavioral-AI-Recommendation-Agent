import os
import time
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

# Global in-memory trace store for Admin Observability Dashboard
AGENT_TRACES = []
MAX_TRACES = 100

class AgentTrace:
    def __init__(self, user_id, session_id, trigger_reason):
        self.trace_id = f"trace_{int(time.time() * 1000)}"
        self.user_id = user_id
        self.session_id = session_id
        self.trigger_reason = trigger_reason
        self.start_time = time.time()
        self.end_time = None
        self.nodes_executed = []
        self.retrieved_candidates = []
        self.intent_summary = ""
        self.llm_prompt = ""
        self.generated_narrative = ""
        self.recommended_product_ids = []
        self.status = "running"
        self.error = None

    def add_node_execution(self, node_name, input_data, output_data, duration_ms=0):
        self.nodes_executed.append({
            'node': node_name,
            'input': input_data,
            'output': output_data,
            'duration_ms': round(duration_ms, 2),
            'timestamp': datetime.utcnow().isoformat()
        })

    def finish(self, narrative, product_ids, status="completed", error=None):
        self.end_time = time.time()
        self.generated_narrative = narrative
        self.recommended_product_ids = product_ids
        self.status = status
        self.error = error
        
        trace_data = self.to_dict()
        AGENT_TRACES.insert(0, trace_data)
        if len(AGENT_TRACES) > MAX_TRACES:
            AGENT_TRACES.pop()
            
        logger.info(f"Agent Trace [{self.trace_id}] finished in {self.total_duration_ms()}ms with status '{status}'")

    def total_duration_ms(self):
        end = self.end_time or time.time()
        return round((end - self.start_time) * 1000, 2)

    def to_dict(self):
        return {
            'trace_id': self.trace_id,
            'user_id': self.user_id,
            'session_id': self.session_id,
            'trigger_reason': self.trigger_reason,
            'start_time': datetime.fromtimestamp(self.start_time).isoformat(),
            'total_duration_ms': self.total_duration_ms(),
            'nodes_executed': self.nodes_executed,
            'retrieved_candidates': self.retrieved_candidates,
            'intent_summary': self.intent_summary,
            'llm_prompt': self.llm_prompt,
            'generated_narrative': self.generated_narrative,
            'recommended_product_ids': self.recommended_product_ids,
            'status': self.status,
            'error': self.error
        }

def get_all_traces(limit=20):
    return AGENT_TRACES[:limit]

def get_trace_by_id(trace_id):
    for t in AGENT_TRACES:
        if t['trace_id'] == trace_id:
            return t
    return None
