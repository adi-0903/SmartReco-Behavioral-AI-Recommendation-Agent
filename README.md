# 🤖 SmartReco — Behavioral AI Recommendation Agent & Masterclass Platform

[![Python 3.11](https://img.shields.io/badge/Python-3.11+-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![Flask](https://img.shields.io/badge/Flask-2.3+-000000?style=for-the-badge&logo=flask&logoColor=white)](https://flask.palletsprojects.com/)
[![NVIDIA NIM](https://img.shields.io/badge/NVIDIA--NIM-Llama--3.1--70B-76B900?style=for-the-badge&logo=nvidia&logoColor=white)](https://build.nvidia.com/)
[![ChromaDB](https://img.shields.io/badge/ChromaDB-Vector--Store-FF6F61?style=for-the-badge)](https://www.trychroma.com/)
[![LangGraph](https://img.shields.io/badge/LangGraph-Agentic--Workflow-121011?style=for-the-badge)](https://langchain-ai.github.io/langgraph/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg?style=for-the-badge)](https://opensource.org/licenses/MIT)

> **SmartReco** is a state-of-the-art, agentic recommendation and learning platform for masterclasses. It continuously observes student behavior (page views, searches, dwell time, hover signals), constructs dynamic weighted intent profiles, semantically retrieves catalog items via a **Dual-Write Vector DB (ChromaDB)**, and powers a universal technical assistant using **NVIDIA Llama 3.1 70B Instruct**.

---

## 🌟 Key Platform Innovations

### 1. 🤖 Universal AI Assistant & Workstation (Powered by NVIDIA NIM)
- **NVIDIA Llama 3.1 70B LLM Integration**: Connected to NVIDIA NIM API (`https://integrate.api.nvidia.com/v1`) using `meta/llama-3.1-70b-instruct` and `meta/llama-3.1-8b-instruct`.
- **RAG-Grounded Answers**: Combines vector retrieval over 31 masterclasses with real-time LLM inference for course recommendations, live coding/debugging, syntax explanations, and tech roadmaps.
- **Dual Interface Design**:
  - 💬 **Floating Glassmorphic Chatbot Widget**: Resizable circular floating widget with **1-click Fullscreen Expansion (`⤢`)**.
  - 💻 **Dedicated AI Workstation (`/assistant`)**: Full-page IDE studio featuring prompt shortcuts, markdown code block formatting, and terminal logs.

### 2. 🎓 Expanded 31 Masterclasses Catalog
- **5 High-Demand Domains**:
  1. **Generative AI & Agentic Systems**: Autonomous Multi-Agent Swarms, LangGraph Workflows, RAG Architectures, VLM Multimodal AI.
  2. **Ethical Hacking & Cybersecurity**: Threat Hunting, Web App Exploitation, Malware Analysis, Reverse Engineering, DevSecOps.
  3. **Fullstack Web Development**: Next.js 14, Microservices (FastAPI/Flask/Docker), Advanced React Server Components, Node.js GraphQL APIs.
  4. **Data Science & Machine Learning**: PyTorch Deep Learning, Big Data Pipelines (Spark/BigQuery), Production MLOps, Time Series Forecasting.
  5. **Cloud & DevOps**: Kubernetes Container Orchestration, AWS Certified Solutions Architect, Terraform IaC, GCP Data Architecture.

### 3. 👥 Admin Onboarding & Student Control Studio (`/admin/students`)
- **Dedicated Admin Portal**: Admins are automatically routed to the **Student Registrations & Onboarding Monitor** instead of the public catalog.
- **Live Student Audit Feed**:
  - Real-time student signup counter.
  - Visual verification badges (`✓ OTP Verified` vs `⌛ Pending OTP`).
  - Account timestamps, total behavioral events count, and enrolled course tags.
  - 1-click **Remove Student** administration capability.

### 4. 📩 Live Gmail SMTP Direct 6-Digit Email OTP Verification
- **Inbox OTP Delivery**: Integrates direct TLS SMTP connection (`smtp.gmail.com:587`) delivering HTML verification emails.
- **Secure Registration Flow**: New users enter 6-digit OTP codes on a glassmorphic portal (`/verify_otp`) before account activation.

### 5. ⚡ Dual-Write Vector Database (ChromaDB + SQLite)
- **Instant Dual-Write**: Every product created, modified, or deleted in SQL automatically syncs to ChromaDB vector storage (`smartreco_products` collection).
- **Feature Hashing Vectorizer**: `FastLightweightEmbeddingFunction` provides deterministic 128-dimensional normalized semantic embeddings with 0 network latency.

### 6. 🧠 LangGraph Agentic Recommendation Engine & Observability
- Multi-node reasoning graph in `agent/workflow.py`:
  1. `analyze_behavior`: Computes category interest weights and decay factors.
  2. `retrieve_products`: Dual RAG vector + metadata retrieval.
  3. `evaluate_retrieval`: Triggers query expansion on low candidate similarity scores.
  4. `generate_persuasion`: Synthesizes persuasive recommendation narratives.
  5. `finalize_recommendation`: Persists recommendation objects and updates caches.
- **Agent Execution Tracing (`/admin/traces`)**: Visual dashboard detailing node execution times, candidate scores, and decision graphs.

### 7. 📊 Non-Blocking Client-Side Event Stream (`tracker.js`)
- Asynchronous listener capturing `page_view`, `product_view`, `search`, `category_filter`, `dwell_time`, and `hover`.
- Transmits events silently every 3 seconds using `navigator.sendBeacon` and `fetch(..., {keepalive: true})`.

### 8. 📧 Proactive Daily Email Digests & Profile Management
- **APScheduler Background Jobs**: Periodically generates personalized course digests logged in `/digests`.
- **Learner Profile (`/profile`)**: Overview header, enrolled masterclasses dashboard, and password change security form.

---

## 🏗️ System Architecture

```mermaid
flowchart TD
    User([Learner / Admin User]) --> Frontend[Glassmorphic HTML5 / CSS3 Interface]
    Frontend --> TrackerJS[static/js/tracker.js Non-blocking Event Stream]
    TrackerJS --> BatchAPI[/api/events/batch/]
    BatchAPI --> SQLite[(SQLite Database: smartreco.db)]
    
    Frontend --> RAGChat[/api/chat NVIDIA AI Assistant]
    RAGChat --> ChromaDB[(ChromaDB Vector Store: ./chroma_db)]
    RAGChat --> NVIDIA[NVIDIA NIM API: Llama 3.1 70B / 8B]
    NVIDIA --> Frontend
    
    Admin([Admin User]) --> AdminStudents[/admin/students Joined Students Portal]
    AdminStudents --> SQLite
    
    SQLite --> LangGraph[LangGraph Agentic Engine: workflow.py]
    ChromaDB --> LangGraph
    LangGraph --> Recs[(Recommendations Table)]
    
    APScheduler[APScheduler Job] --> DigestEngine[Email Service: email_service.py]
    DigestEngine --> GmailSMTP[Gmail Live SMTP TLS]
    GmailSMTP --> UserInbox([User Inbox 6-Digit OTP])
```

---

## 🛠️ Technology Stack

| Layer | Technologies Used |
| :--- | :--- |
| **Backend Engine** | Python 3.11, Flask, SQLAlchemy ORM, APScheduler, HTTPX |
| **LLM & AI Framework** | NVIDIA NIM API (`meta/llama-3.1-70b-instruct`, `meta/llama-3.1-8b-instruct`), LangGraph |
| **Vector Database** | ChromaDB Persistent Storage (Cosine HNSW Space, Custom Hashing Vectorizer) |
| **Database Storage** | SQLite (`smartreco.db`) |
| **Email Delivery** | Direct Live Gmail SMTP (`smtplib`, MIME HTML Templates, TLS 587) |
| **Frontend Stack** | HTML5 Semantic Markup, Vanilla CSS3 (Glassmorphic Theme), JavaScript ES6+ |
| **Security & Auth** | Werkzeug Password Hashing, 6-Digit Email OTP Verification, Session Auth |
| **Testing & CI** | 36-Step In-and-Out Automated Integration Suite (`test_smartreco_suite.py`) |

---

## ⚙️ Quickstart & Setup Guide

### 1. Repository Setup
```bash
git clone https://github.com/adi-0903/SmartReco-Behavioral-AI-Recommendation-Agent.git
cd SmartReco-Behavioral-AI-Recommendation-Agent
```

### 2. Virtual Environment & Dependencies
```bash
# Create virtual environment
python -m venv venv

# Activate on Windows PowerShell:
.\venv\Scripts\activate

# Activate on Linux / macOS:
source venv/bin/activate

# Install required packages
pip install -r requirements.txt
```

### 3. Environment Variables Configuration (`.env`)
Create a `.env` file in the root project directory:

```env
# NVIDIA NIM AI Chatbot Configuration
NVIDIA_API_KEY=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
NVIDIA_BASE_URL=https://integrate.api.nvidia.com/v1
NVIDIA_MODEL=meta/llama-3.1-70b-instruct

# Gmail Live SMTP Credentials for Direct OTP Email Delivery
MAIL_SERVER=smtp.gmail.com
MAIL_PORT=587
MAIL_USERNAME=singhaladitya619@gmail.com
MAIL_PASSWORD=mjczusmtumazvwxf
MAIL_DEFAULT_SENDER=singhaladitya619@gmail.com

# Core Flask App Secret
SECRET_KEY=smartreco_secret_key_super_secure_12345
FLASK_ENV=development
PORT=5000
```

### 4. Launch the Application
```bash
python app.py
```
Open your browser and navigate to: **`http://127.0.0.1:5000`**

---

## 🔑 Access Roles & Credentials

| Role | Portal URL | Credentials | Capabilities |
| :--- | :--- | :--- | :--- |
| **Catalog Admin** | `/admin/students` | Email: `admin@smartreco.com`<br>Password: `admin` | View joined students, OTP verification badges, remove students, inspect behavior stream, agent traces & digest controls. |
| **Learner User** | `/register` | *Public Self-Registration* | Register via email, verify 6-digit OTP code, explore masterclasses, chat with NVIDIA AI Workstation, enroll, view profile & change password. |

---

## 🧪 Comprehensive Verification Suite

Run the full automated integration test suite covering 36 critical system operations:

```bash
python test_smartreco_suite.py
```

### Verification Suite Coverage (36/36 Tests):
- ✅ Catalog Homepage & Database Seed Verification
- ✅ ChromaDB Dual-Write Vector Store Embedding Synchronization
- ✅ Admin Authentication & Role-Based Access Control
- ✅ Admin Joined Students Portal (`/admin/students`) Rendering
- ✅ 6-Digit Email OTP Registration & Verification Workflow
- ✅ Learner Profile Portal (`/profile`) & Course Enrollment System
- ✅ NVIDIA NIM Llama 3.1 AI Advisor RAG Chatbot API (`/api/chat`)
- ✅ Dedicated Full-Page AI Assistant Workstation (`/assistant`)
- ✅ Non-blocking Behavioral Event Batching (`/api/events/batch`)
- ✅ Dual-Write Product CRUD Operations (SQL + ChromaDB)
- ✅ LangGraph Agentic Workflow & Observability Trace Recording (`/admin/traces`)
- ✅ Strict Student Intent Recommendation Filtering
- ✅ Proactive Email Digest Generation (`APScheduler`)
- ✅ Automatic Test Suite User Cleanup & Database Purging

---

## 📄 License
Distributed under the **MIT License**. See `LICENSE` for details.
