import logging
from models import db, User, Product, Event, Recommendation
from vector_store import vector_store

logger = logging.getLogger(__name__)

COURSES_SEED = [
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

    user = User.query.filter_by(email='user@smartreco.com').first()
    if not user:
        user = User(email='user@smartreco.com', name='Alex Tech Learner', role='user')
        user.set_password('user123')
        db.session.add(user)

    db.session.commit()

    # 2. Seed Products
    for c_data in COURSES_SEED:
        existing = Product.query.filter_by(title=c_data['title']).first()
        if not existing:
            prod = Product(**c_data)
            db.session.add(prod)
    db.session.commit()
    logger.info("SQL Product Catalog seeded with rich multi-category courses.")

    # 3. Dual-Write sync all products into ChromaDB Vector Store
    all_products = Product.query.all()
    synced_count = vector_store.sync_all_products(all_products)
    logger.info(f"Vector Store Dual-Write initialized: Synced {synced_count}/{len(all_products)} products.")

    # 4. Seed initial sample behavioral events for default user
    if Event.query.count() == 0 and user:
        p_agent = Product.query.filter(Product.title.like("%Agentic%")).first()
        p_vector = Product.query.filter(Product.title.like("%Vector%")).first()
        
        sample_events = [
            Event(
                user_id=user.id,
                session_id="init_sess_001",
                event_type="search",
                target_id="Agentic AI",
                details_json='{"query": "Agentic AI LangGraph autonomous workflow"}',
                duration_ms=0
            ),
            Event(
                user_id=user.id,
                session_id="init_sess_001",
                event_type="product_view",
                target_id=str(p_agent.id) if p_agent else "1",
                details_json=f'{{"product_title": "{p_agent.title if p_agent else "Agentic AI"}", "category": "Generative AI & Agents"}}',
                duration_ms=45000
            ),
            Event(
                user_id=user.id,
                session_id="init_sess_001",
                event_type="product_view",
                target_id=str(p_vector.id) if p_vector else "2",
                details_json=f'{{"product_title": "{p_vector.title if p_vector else "Vector Search"}", "category": "Generative AI & Agents"}}',
                duration_ms=30000
            )
        ]
        db.session.add_all(sample_events)
        db.session.commit()
        logger.info("Sample user behavioral events seeded.")
