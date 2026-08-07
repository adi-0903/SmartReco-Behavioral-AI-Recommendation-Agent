# SmartReco — Behavioral AI Recommendation Agent

**SmartReco** is an agentic recommendation platform for an online learning marketplace. It continuously observes user behavior (page views, search queries, dwell time, product interactions), builds a dynamic user intent profile, semantically retrieves matching catalog products using a **dual-write Vector DB (ChromaDB)**, and generates personalized, persuasive recommendation copy via **Mesh API (GPT-4o)**.

---

## 🚀 Key Architectural Features

### 1. Dual-Write Product Catalog Sync
- **SQL Database + Vector DB**: Every catalog creation, update, or deletion in the admin dashboard executes a dual-write operation to both SQLite (`products` table) and ChromaDB persistent vector storage (`smartreco_products` collection).
- **Semantic Catalog Retrieval**: Products are vectorized using title, category, description, and tags to enable true RAG-grounded recommendations.

### 2. Non-Blocking Client-Side Event Tracking
- **Asynchronous Event Queue**: `static/js/tracker.js` intercepts user actions (`page_view`, `product_view`, `search`, `category_filter`, `dwell_time`, `click_recommendation`).
- **Batched & Beacon Delivery**: Flushes event queues every 3 seconds or on tab unload using `navigator.sendBeacon` and `fetch(..., {keepalive: true})`, preventing any frontend freeze or lag.

### 3. Agentic Recommendation Engine (LangGraph & RAG)
Built as a structured multi-node reasoning graph in `agent/workflow.py`:
1. **`analyze_behavior`**: Aggregates recent user behavioral signals, computes interest weights per category, and formulates search query & intent summary.
2. **`retrieve_products`**: Executes semantic vector retrieval over ChromaDB + SQL candidate matching.
3. **`evaluate_retrieval`**: Evaluates similarity score & candidate coverage; triggers query expansion if candidate scores are below threshold.
4. **`generate_persuasion`**: Calls **Mesh API** (`https://api.meshapi.ai/v1`) using model `openai/gpt-4o` to craft a personalized 2-paragraph persuasive narrative explaining *why* these courses fit the user's specific learning path.
5. **`finalize_recommendation`**: Formats structured recommendation object, persists to SQLite DB, and caches result.

---

## 🌟 Highlighted Bonus Features Implemented

- ⭐ **Structured Agent Framework (LangGraph)**: Multi-node workflow dividing behavior analysis, vector retrieval, retrieval evaluation/refinement, and Mesh API LLM generation into explicit graph nodes.
- ⭐ **Scheduled Proactive Delivery (APScheduler)**: Background scheduler periodically evaluates active user sessions, runs the agentic recommendation engine, generates a personalized daily email digest with persuasive HTML copy, and logs sent digests.
- ⭐ **Agent Execution Tracing & Observability**: Real-time admin dashboard at `/admin/traces` detailing step-by-step node execution times, vector match scores, intent summaries, and LLM prompt history.
- ⭐ **Retrieval Polish**: Hybrid vector search + metadata category filtering + automatic query expansion on low similarity scores.

---

## 🛠️ Tech Stack

- **Backend**: Python 3.11, Flask, SQLAlchemy, APScheduler
- **LLM Gateway**: Mesh API (`base_url="https://api.meshapi.ai/v1"`, `model="openai/gpt-4o"`)
- **Vector Database**: ChromaDB (Cosine distance vector store)
- **Frontend**: Jinja2 Templates, Vanilla CSS (Dark Mode Design System), Custom Event Tracking JS
- **Database**: SQLite / SQLAlchemy ORM

---

## ⚙️ Setup & Local Installation

### 1. Clone & Install Dependencies
```bash
git clone <your-repo-url>
cd SmartReco
python -m venv venv
# On Windows:
venv\Scripts\activate
# On Linux/macOS:
source venv/bin/activate

pip install -r requirements.txt
```

### 2. Environment Variables Configuration
Create a `.env` file in the root directory (included in `.gitignore`):
```env
MESH_API_KEY=rsk_your_mesh_api_key_here
MESH_BASE_URL=https://api.meshapi.ai/v1
MESH_MODEL=openai/gpt-4o
SECRET_KEY=smartreco_secret_key_super_secure
PORT=5000
```

### 3. Run the Application
```bash
python app.py
```
Open your browser and navigate to: **`http://127.0.0.1:5000`**

---

## 🔑 Demo Account Credentials

| Role | Email | Password | Access Capabilities |
| :--- | :--- | :--- | :--- |
| **Learner User** | `user@smartreco.com` | `user123` | Explore courses, search, dwell time tracking, dynamic AI recommendations |
| **Catalog Admin** | `admin@smartreco.com` | `admin` | Dual-write catalog portal, behavioral event stream, agent trace logs |

---

## 🧪 Automated CI Workflow Checks

The repository includes `.github/workflows/smartreco-checks.yml` as required by the hackathon submission guidelines.

Ensure the following GitHub Repository Secrets are set:
- `MESH_API_KEY`: Your Mesh API key (starts with `rsk_`)
- `SUBMISSION_TOKEN`: Your hackathon submission token
