import logging
from models import db, User, Product, Event, Recommendation
from vector_store import vector_store

logger = logging.getLogger(__name__)

COURSES_SEED = [
    # -------------------------------------------------------------
    # 1. GENERATIVE AI & AUTONOMOUS AGENTS (6 Courses)
    # -------------------------------------------------------------
    {
        "title": "Mastering Agentic AI & LangGraph Workflows",
        "description": "Build production-grade autonomous agent systems with multi-agent orchestration, tool use, human-in-the-loop reflection, and dynamic RAG memory architectures using Python and LangGraph.",
        "category": "Generative AI & Agents",
        "price": 89.99,
        "rating": 4.9,
        "tags": "Agentic AI, LangGraph, Python, RAG, LLM, OpenAI, Vectors",
        "image_url": "https://picsum.photos/seed/agentic_ai/400/250"
    },
    {
        "title": "Advanced Vector Search & RAG Architectures",
        "description": "Learn semantic retrieval, hybrid keyword-vector indexing, re-ranking algorithms, metadata filtering, and chunk optimization with ChromaDB, Pinecone, and Qdrant.",
        "category": "Generative AI & Agents",
        "price": 79.99,
        "rating": 4.8,
        "tags": "Vector DB, RAG, ChromaDB, Embeddings, Search, NLP",
        "image_url": "https://picsum.photos/seed/vector_rag/400/250"
    },
    {
        "title": "LLM Fine-Tuning & Quantization Techniques",
        "description": "Train custom open-source Large Language Models using QLoRA, Axolotl, Unsloth, llama.cpp, and vLLM inference server acceleration.",
        "category": "Generative AI & Agents",
        "price": 99.99,
        "rating": 4.9,
        "tags": "LLM, Fine-Tuning, LoRA, Open Source, Llama, AI",
        "image_url": "https://picsum.photos/seed/llm_tune/400/250"
    },
    {
        "title": "Multi-Agent Systems & Swarm Intelligence Engineering",
        "description": "Architect complex multi-agent swarms with AutoGen, CrewAI, and LangChain for automated code generation, complex research synthesis, and enterprise workflows.",
        "category": "Generative AI & Agents",
        "price": 109.99,
        "rating": 4.9,
        "tags": "Multi-Agent, AutoGen, CrewAI, Swarm Intelligence, Python",
        "image_url": "https://picsum.photos/seed/swarm_ai/400/250"
    },
    {
        "title": "Production Prompt Engineering & Function Calling",
        "description": "Master structured JSON output generation, tool-use bindings, zero-shot/few-shot prompting patterns, guardrails, and automated LLM benchmarking.",
        "category": "Generative AI & Agents",
        "price": 69.99,
        "rating": 4.7,
        "tags": "Prompt Engineering, Function Calling, OpenAI, JSON, Guardrails",
        "image_url": "https://picsum.photos/seed/prompt_eng/400/250"
    },
    {
        "title": "Multimodal AI & Vision Language Models (VLM)",
        "description": "Develop next-gen AI applications combining computer vision, audio processing, and spatial reasoning with GPT-4 Vision, Claude 3.5 Sonnet, and Gemini 1.5 Pro.",
        "category": "Generative AI & Agents",
        "price": 94.99,
        "rating": 4.8,
        "tags": "Multimodal AI, Computer Vision, VLM, GPT-4V, Gemini, Audio AI",
        "image_url": "https://picsum.photos/seed/multimodal/400/250"
    },

    # -------------------------------------------------------------
    # 2. CYBERSECURITY & OFFENSIVE SECURITY (6 Courses)
    # -------------------------------------------------------------
    {
        "title": "Ethical Hacking & Offensive Cyber Security",
        "description": "Learn network penetration testing, web app vulnerability scanning, reverse engineering, exploit development, and SOC threat monitoring.",
        "category": "Cybersecurity",
        "price": 99.99,
        "rating": 4.8,
        "tags": "Cybersecurity, Hacking, Penetration Testing, Network, Security, Vulnerability",
        "image_url": "https://picsum.photos/seed/security/400/250"
    },
    {
        "title": "Cloud Security & Threat Hunting Masterclass",
        "description": "Protect AWS, GCP, and Azure cloud infrastructure with IAM policies, SOC log auditing, container security, incident response, and zero-trust security architecture.",
        "category": "Cybersecurity",
        "price": 89.99,
        "rating": 4.9,
        "tags": "Cybersecurity, Cloud Security, Threat Hunting, AWS, Zero Trust, Incident Response",
        "image_url": "https://picsum.photos/seed/cloud_sec/400/250"
    },
    {
        "title": "Web Application Hacking & Bug Bounty Essentials",
        "description": "Master OWASP Top 10 web vulnerabilities including SQL Injection, Cross-Site Scripting (XSS), CSRF, Authentication Bypass, and automated vulnerability scanning tools.",
        "category": "Cybersecurity",
        "price": 79.99,
        "rating": 4.8,
        "tags": "Cybersecurity, Web Security, Hacking, OWASP, Bug Bounty, Penetration Testing",
        "image_url": "https://picsum.photos/seed/bug_bounty/400/250"
    },
    {
        "title": "Malware Analysis & Reverse Engineering Fundamentals",
        "description": "Decompile malicious binaries, analyze ransomware behaviors, debug x86/x64 assembly language code with Ghidra and IDA Pro in isolated sandbox environments.",
        "category": "Cybersecurity",
        "price": 104.99,
        "rating": 4.9,
        "tags": "Malware Analysis, Reverse Engineering, Ghidra, Assembly, Security, Forensics",
        "image_url": "https://picsum.photos/seed/malware/400/250"
    },
    {
        "title": "Network Vulnerability Assessment & Wireshark Defense",
        "description": "Sniff network packets, analyze TCP/IP handshake anomalies, mitigate DDoS attacks, configure intrusion detection systems (Snort/Zeek), and firewall rules.",
        "category": "Cybersecurity",
        "price": 74.99,
        "rating": 4.7,
        "tags": "Network Security, Wireshark, IDS, Firewall, Packet Analysis, Defense",
        "image_url": "https://picsum.photos/seed/network_sec/400/250"
    },
    {
        "title": "DevSecOps & Automated Security Pipeline Integration",
        "description": "Integrate SAST/DAST security scanning, secret detection, dependencies vulnerability auditing (Snyk, Trivy), and container scanning into GitHub Actions CI/CD.",
        "category": "Cybersecurity",
        "price": 84.99,
        "rating": 4.8,
        "tags": "DevSecOps, CI/CD, SAST, DAST, Container Security, Snyk, GitHub Actions",
        "image_url": "https://picsum.photos/seed/devsecops/400/250"
    },

    # -------------------------------------------------------------
    # 3. WEB DEVELOPMENT & FULLSTACK ARCHITECTURE (6 Courses)
    # -------------------------------------------------------------
    {
        "title": "Fullstack Next.js 14 & AI Application Masterclass",
        "description": "Develop high-performance modern web apps with React, Next.js App Router, Tailwind CSS, TypeScript, Server Actions, and real-time streaming AI chat interfaces.",
        "category": "Web Development & Fullstack",
        "price": 69.99,
        "rating": 4.7,
        "tags": "Next.js, React, Web Dev, TypeScript, Tailwind, Fullstack",
        "image_url": "https://picsum.photos/seed/nextjs/400/250"
    },
    {
        "title": "Production Microservices with Flask, FastAPI & Docker",
        "description": "Design resilient backend APIs with Python, FastAPI, Flask, AsyncIO, SQL database migrations, Redis caching, and Kubernetes deployment pipelines.",
        "category": "Web Development & Fullstack",
        "price": 74.99,
        "rating": 4.8,
        "tags": "Python, Flask, FastAPI, Docker, Microservices, API",
        "image_url": "https://picsum.photos/seed/fastapi/400/250"
    },
    {
        "title": "Advanced React, Server Components & State Management",
        "description": "Master React 18 Concurrent Rendering, Suspense boundaries, Zustand, Redux Toolkit, React Query, performance profiling, and custom hook design.",
        "category": "Web Development & Fullstack",
        "price": 64.99,
        "rating": 4.8,
        "tags": "React, Frontend, State Management, TypeScript, Performance",
        "image_url": "https://picsum.photos/seed/react/400/250"
    },
    {
        "title": "Node.js & GraphQL Enterprise API Architecture",
        "description": "Build high-throughput backend services using Node.js, Express, Apollo GraphQL, Prisma ORM, WebSockets, rate limiting, and JWT authentication.",
        "category": "Web Development & Fullstack",
        "price": 79.99,
        "rating": 4.7,
        "tags": "Node.js, GraphQL, Express, Prisma, Backend, WebSockets",
        "image_url": "https://picsum.photos/seed/nodejs/400/250"
    },
    {
        "title": "Modern Frontend UI/UX Design System with Tailwind CSS",
        "description": "Construct gorgeous dark-mode glassmorphic user interfaces, dynamic micro-animations, accessible ARIA components, and responsive grid layouts.",
        "category": "Web Development & Fullstack",
        "price": 59.99,
        "rating": 4.9,
        "tags": "Tailwind CSS, UI/UX, Glassmorphism, CSS3, Web Design",
        "image_url": "https://picsum.photos/seed/ui_design/400/250"
    },
    {
        "title": "Scalable Relational & NoSQL Database Engineering",
        "description": "Master SQL query performance tuning, index optimization, PostgreSQL partitioning, MongoDB sharding, Redis caching, and ACID transaction isolation.",
        "category": "Web Development & Fullstack",
        "price": 84.99,
        "rating": 4.8,
        "tags": "PostgreSQL, SQL, MongoDB, Database, Redis, Performance",
        "image_url": "https://picsum.photos/seed/db_eng/400/250"
    },

    # -------------------------------------------------------------
    # 4. DATA SCIENCE & MACHINE LEARNING (6 Courses)
    # -------------------------------------------------------------
    {
        "title": "Deep Learning & PyTorch Model Fine-Tuning",
        "description": "Master deep neural networks, computer vision, Transformer architectures, LoRA fine-tuning, quantization, and PyTorch model deployment on GPU clusters.",
        "category": "Data Science & Machine Learning",
        "price": 94.99,
        "rating": 4.9,
        "tags": "Deep Learning, PyTorch, Transformers, Model Fine-Tuning, ML",
        "image_url": "https://picsum.photos/seed/pytorch/400/250"
    },
    {
        "title": "Data Engineering & Big Data Pipelines with Spark & BigQuery",
        "description": "Build scalable data lakes, real-time streaming pipelines, dbt models, Apache Spark jobs, and Google Cloud BigQuery data warehouse pipelines.",
        "category": "Data Science & Machine Learning",
        "price": 84.99,
        "rating": 4.7,
        "tags": "Data Engineering, Spark, BigQuery, SQL, ETL, Python",
        "image_url": "https://picsum.photos/seed/data_eng/400/250"
    },
    {
        "title": "Production MLOps: Model Monitoring & Feature Stores",
        "description": "Deploy machine learning pipelines with MLflow, Kubeflow, Feast feature stores, automated retraining triggers, data drift detection, and BentoML inference.",
        "category": "Data Science & Machine Learning",
        "price": 89.99,
        "rating": 4.8,
        "tags": "MLOps, MLflow, Feature Store, Data Drift, Python, Deployment",
        "image_url": "https://picsum.photos/seed/mlops/400/250"
    },
    {
        "title": "Time Series Forecasting & Statistical Predictive Modeling",
        "description": "Predict financial trends and demand using ARIMA, Prophet, XGBoost time series, LSTM recurrent networks, and anomaly detection algorithms.",
        "category": "Data Science & Machine Learning",
        "price": 79.99,
        "rating": 4.7,
        "tags": "Time Series, Forecasting, XGBoost, Statistics, Python, Pandas",
        "image_url": "https://picsum.photos/seed/timeseries/400/250"
    },
    {
        "title": "Natural Language Processing (NLP) with Hugging Face",
        "description": "Fine-tune BERT, RoBERTa, and T5 models for sentiment analysis, named entity recognition, text classification, and semantic embedding search.",
        "category": "Data Science & Machine Learning",
        "price": 89.99,
        "rating": 4.9,
        "tags": "NLP, Hugging Face, BERT, Transformers, Text Analytics, Python",
        "image_url": "https://picsum.photos/seed/nlp/400/250"
    },
    {
        "title": "Applied Machine Learning with Scikit-Learn & XGBoost",
        "description": "Practical guide to supervised and unsupervised ML: decision trees, random forests, gradient boosting, hyperparameter tuning, and cross-validation.",
        "category": "Data Science & Machine Learning",
        "price": 69.99,
        "rating": 4.8,
        "tags": "Machine Learning, Scikit-Learn, XGBoost, Python, Data Science",
        "image_url": "https://picsum.photos/seed/scikit/400/250"
    },

    # -------------------------------------------------------------
    # 5. CLOUD, MICROSERVICES & DEVOPS (6 Courses)
    # -------------------------------------------------------------
    {
        "title": "Kubernetes & Cloud Native DevOps Engineering",
        "description": "Hands-on guide to container orchestration, Helm charts, Terraform infrastructure as code, Prometheus monitoring, and CI/CD GitOps with ArgoCD.",
        "category": "Cloud & DevOps",
        "price": 79.99,
        "rating": 4.8,
        "tags": "Kubernetes, Docker, DevOps, Cloud, Terraform, CI/CD",
        "image_url": "https://picsum.photos/seed/k8s/400/250"
    },
    {
        "title": "AWS Certified Solutions Architect Professional",
        "description": "Comprehensive preparation for AWS Solution Architect exam covering VPC networking, IAM security, Serverless Lambda, DynamoDB, and multi-region resilience.",
        "category": "Cloud & DevOps",
        "price": 89.99,
        "rating": 4.9,
        "tags": "AWS, Cloud, Architecture, Security, Serverless",
        "image_url": "https://picsum.photos/seed/aws/400/250"
    },
    {
        "title": "Terraform & Multi-Cloud Infrastructure Automation",
        "description": "Write reusable infrastructure as code modules for AWS, Google Cloud, and Azure with state locks, HCL language syntax, and automated plan reviews.",
        "category": "Cloud & DevOps",
        "price": 74.99,
        "rating": 4.8,
        "tags": "Terraform, IaC, Cloud, AWS, GCP, DevOps",
        "image_url": "https://picsum.photos/seed/terraform/400/250"
    },
    {
        "title": "Docker Container Masterclass & Security Hardening",
        "description": "Master multi-stage Dockerfiles, image size reduction, rootless container security, network isolation, compose stacks, and private registry management.",
        "category": "Cloud & DevOps",
        "price": 64.99,
        "rating": 4.7,
        "tags": "Docker, Containers, DevOps, Security, Linux",
        "image_url": "https://picsum.photos/seed/docker/400/250"
    },
    {
        "title": "Google Cloud Platform (GCP) Data Engineering & Architecture",
        "description": "Architect cloud data solutions with Cloud Storage, Cloud Spanner, Pub/Sub event streams, Dataproc Spark clusters, and BigQuery analytics engines.",
        "category": "Cloud & DevOps",
        "price": 84.99,
        "rating": 4.8,
        "tags": "GCP, Google Cloud, BigQuery, PubSub, Data Lakes",
        "image_url": "https://picsum.photos/seed/gcp/400/250"
    },
    {
        "title": "Site Reliability Engineering (SRE) & Observability with Grafana",
        "description": "Implement Service Level Objectives (SLOs), error budgets, distributed tracing with OpenTelemetry, Prometheus alertmanager, and Grafana dashboards.",
        "category": "Cloud & DevOps",
        "price": 89.99,
        "rating": 4.9,
        "tags": "SRE, Grafana, Prometheus, OpenTelemetry, Observability, DevOps",
        "image_url": "https://picsum.photos/seed/sre/400/250"
    }
]

def seed_database():
    """Seeds initial database tables and synchronizes vector store."""
    logger.info("Checking database seed status...")
    
    # 1. Seed Users if not present
    admin = User.query.filter_by(email='admin@smartreco.com').first()
    if not admin:
        admin = User(email='admin@smartreco.com', name='System Admin', role='admin')
        admin.set_password('admin')
        db.session.add(admin)

    db.session.commit()

    # 2. Seed Products
    seeded_new = 0
    for c_data in COURSES_SEED:
        existing = Product.query.filter_by(title=c_data['title']).first()
        if not existing:
            prod = Product(**c_data)
            db.session.add(prod)
            seeded_new += 1
    db.session.commit()
    logger.info(f"SQL Product Catalog seeded with {len(COURSES_SEED)} rich multi-category masterclasses ({seeded_new} newly added).")

    # 3. Dual-Write sync all products into ChromaDB Vector Store
    all_products = Product.query.all()
    synced_count = vector_store.sync_all_products(all_products)
    logger.info(f"Vector Store Dual-Write initialized: Synced {synced_count}/{len(all_products)} products.")
