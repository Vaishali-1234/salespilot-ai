# SalesPilot AI — System & Production Scalability Architecture

## 1. Layered MVP Architecture

SalesPilot AI is engineered with strict separation of concerns across five layers:

```
┌───────────────────────────────────────────────────────────────────────────┐
│                  PRESENTATION LAYER (Streamlit SaaS UI)                   │
│  Overview │ Live Voice Agent │ CRM │ Knowledge Base │ Appts │ BI Analytics│
└───────────────────────────────────┬───────────────────────────────────────┘
                                    │ HTTP / REST + Multipart Audio
┌───────────────────────────────────▼───────────────────────────────────────┐
│                   API GATEWAY LAYER (FastAPI + Pydantic)                  │
│  /api/sessions │ /api/leads │ /api/appointments │ /api/knowledge │ /health│
└──────┬──────────────────────┬───────────────────────┬─────────────────────┘
       │                      │                       │
┌──────▼──────────┐   ┌───────▼──────────┐   ┌────────▼─────────────────────┐
│   VOICE LAYER   │   │    AI ENGINE     │   │          RAG LAYER           │
│ Faster-Whisper  │   │ SalesPilotAgent  │   │ LangChain TextSplitter       │
│ (STT)           │   │ Gemini 2.5 Flash │   │ SentenceTransformers MiniLM  │
│ Edge TTS        │   │ Memory / BANT    │   │ FAISS IndexFlatIP (Cosine)   │
│ (Neural Speech) │   │ Sentiment/Summary│   │ Anti-Hallucination Threshold │
└─────────────────┘   └───────┬──────────┘   └──────────────────────────────┘
                              │
┌─────────────────────────────▼─────────────────────────────────────────────┐
│                   PERSISTENCE LAYER (SQLAlchemy + SQLite)                 │
│     Leads │ CallSessions │ Messages │ Appointments │ CallSummaries        │
└───────────────────────────────────────────────────────────────────────────┘
```

## 2. Core Agent Tool Registry

The `SalesPilotAgent` orchestrator (`ai_engine/agent.py`) coordinates 9 explicit tools:
1. `retrieve_company_information()` — FAISS cosine search over TechNova Solutions docs with source provenance.
2. `extract_customer_details()` — Strict CRM entity extraction (returns `null` for unmentioned fields).
3. `qualify_lead()` — Transparent 0–100 BANT scoring (Intent/Need 30, Budget 25, Timeline 25, Authority 20).
4. `analyse_sentiment()` — Turn-level sentiment, engagement, purchase intent, urgency, and objection detection.
5. `search_crm()` — Query existing SQLite CRM leads.
6. `create_or_update_lead()` — Persist extracted fields, scores, and pipeline status.
7. `check_appointment_availability()` — Query open consultation slots for a target date.
8. `book_appointment()` — Confirmation-gated booking with SQLite double-booking prevention.
9. `generate_call_summary()` — Post-call structured executive summary saved to CRM.

## 3. Production Scalability Strategy (Scaling to 100,000 Users)

> **Honest Scope Note:** The local MVP uses single-node FastAPI + SQLite + local FAISS + in-process Whisper/TTS, designed for single-user / small-team evaluation. Scaling to **100,000 concurrent/monthly active users** requires the following production architecture:

| Component | Local MVP | Production Architecture (100,000 Users) |
|---|---|---|
| **Frontend & API** | Single Streamlit + Uvicorn process | Containerized Docker pods on Kubernetes (EKS/GKE) behind NGINX/ALB with Horizontal Pod Autoscaling (HPA) |
| **Session Memory & Cache** | SQLite queries per turn | **Redis Cluster** for sub-millisecond active session state, rate limiting, and semantic response caching |
| **CRM & Appointments DB** | SQLite file (`salespilot_crm.db`) | **Managed PostgreSQL** (Primary + Read Replicas) with connection pooling (`PgBouncer`) & row-level locks on slot booking |
| **Vector Search (RAG)** | Local `faiss-cpu` file index | Managed distributed vector DB (**Qdrant Cloud / Pinecone / pgvector**) with tenant/namespace isolation |
| **Voice Processing (STT/TTS)** | In-request Whisper CPU + Edge TTS | Dedicated **GPU Worker Pool** (Whisper `large-v3` on T4/L4 GPUs) fed by **RabbitMQ / Kafka / Celery** async queues + WebRTC streaming |
| **Observability** | Python `logging` | Prometheus + Grafana dashboards, OpenTelemetry distributed tracing, structured JSON logs in ELK/CloudWatch |
| **Security & Compliance** | `.env` secrets & Pydantic validation | Secrets Manager (AWS/GCP), TLS 1.3, AES-256 at rest, OAuth2/JWT RBAC, PII redaction, GDPR/DPDP audit trails |

## 4. Infrastructure & Operational Cost Considerations

- **LLM Token Optimization:** Route simple intent/sentiment checks to lightweight models (`gemini-2.5-flash`) and cache frequent FAQ RAG responses in Redis to cut LLM spend by ~40–60%.
- **Voice Compute Sizing:** Batch/stream STT on spot GPU workers with VAD (Voice Activity Detection) filtering silence before inference.
- **Estimated Monthly Cloud Run-Rate (100k MAU, ~300k voice minutes/mo):**
  - Kubernetes API/UI Nodes: ~\$400–\$700/mo
  - Managed PostgreSQL + Redis: ~\$250–\$450/mo
  - GPU STT Workers + Managed Vector DB: ~\$600–\$1,200/mo
  - LLM & Neural TTS API Usage: Usage-based (~\$0.002–\$0.015 per conversation depending on turn count).
