# SalesPilot AI — Complete Technical Interview Study Guide

Use this guide to master every module, design decision, data flow, and scalability trade-off in **SalesPilot AI** so you can defend the architecture in your 3rd-round technical interview.

---

## 1. 60-Second Elevator Pitch (How to Introduce the Project)

> "SalesPilot AI is an autonomous, voice-first B2B AI sales representative built for a simulated enterprise tech firm, TechNova Solutions. It has a 5-layer decoupled architecture: a Streamlit SaaS frontend with native microphone capture and animated voice UI; a FastAPI REST gateway; a local Faster-Whisper STT and Edge TTS voice layer; a tool-orchestrating AI agent powered by Gemini 2.5 Flash, LangChain, SentenceTransformers, and FAISS; and a SQLite CRM with Plotly BI analytics. Every conversation is session-isolated, grounded in company documents with source citations, transparently qualified from 0 to 100 using BANT criteria, and guarded by confirmation and double-booking checks before creating appointments."

---

## 2. File-by-File Code Map (What Lives Where & Why)

### A. Backend & Config (`backend/`)
- **`backend/config.py`**:
  - Uses `pydantic_settings.BaseSettings` to load typed config from `.env` (`GEMINI_API_KEY`, `GEMINI_MODEL`, `WHISPER_MODEL_SIZE`, `EDGE_TTS_VOICE`, `DATABASE_URL`).
  - Sets `KMP_DUPLICATE_LIB_OK=TRUE` and `OMP_NUM_THREADS=1` at startup so C++ OpenMP libraries used by `faiss-cpu`, `torch`, and `ctranslate2` do not clash on Windows.
- **`backend/main.py`**:
  - FastAPI entrypoint with `@asynccontextmanager async def lifespan(app)` that calls `init_db()` (creates SQLite tables) and `default_retriever.ensure_ready()` (loads or builds the FAISS index).
  - Exposes `GET /health` returning live system telemetry (`llm_status`, `embedding_mode`, `total_kb_chunks`, `whisper_model`, `edge_tts_voice`).
- **`backend/schemas/api_schemas.py`**:
  - Pydantic v2 request validation (regex date check `^\d{4}-\d{2}-\d{2}$`, length bounds, valid `mode` `"voice"|"text"`).
- **`backend/routes/api.py`**:
  - All REST endpoints (`/api/sessions`, `/api/sessions/{id}/chat`, `/api/sessions/{id}/voice`, `/api/sessions/{id}/end`, `/api/leads`, `/api/appointments`, `/api/knowledge`, `/api/analytics`, `/api/settings/config`).
  - Uses FastAPI dependency injection `db: Session = Depends(get_db)` for clean per-request SQLAlchemy session scoping.

### B. Persistence & CRM (`crm/`)
- **`crm/database.py`**:
  - SQLAlchemy engine (`check_same_thread=False` for SQLite with FastAPI worker threads) and `SessionLocal` factory.
- **`crm/models.py`** (5 normalized tables):
  1. `Lead`: Contact info, company, industry, interested service, budget, requirement, timeline, authority, `lead_score` (0–100), `lead_category` (`Hot`/`Warm`/`Cold`), `score_reasoning`, `status`, `overall_sentiment`.
  2. `CallSession`: Primary key `sp-<10hex>`, FK to `Lead.id`, `mode` (`voice`/`text`), `ai_mode` (`gemini`/`demo_fallback`), timestamps.
  3. `Message`: FK to `CallSession.id`, role, content, per-turn `sentiment`, `engagement`, `purchase_intent`, `urgency`, JSON-serialized `objections`, `rag_sources`, `tool_events`, `latency_ms`.
  4. `Appointment`: FK to `Lead.id`, date, time, topic, `status` (`Confirmed`/`Cancelled`), `confirmed_by_customer`.
  5. `CallSummary`: 1-to-1 with `CallSession`, storing post-call executive brief, objections, qualification, appointment status, and next action.
- **`crm/operations.py`**:
  - CRUD for leads (`search_leads` with SQL `ILIKE` search + category/status filters).
  - **Double-booking prevention** in `book_appointment_record()`:
    1. Rejects if `confirmed_by_customer` is `False`.
    2. Rejects if `customer_name` or `customer_email` is missing/invalid.
    3. Queries `Appointment` where `(appointment_date, appointment_time, status == "Confirmed")` — if a row exists, returns a conflict error.
    4. Automatically updates the linked `Lead.status` to `"Demo Scheduled"`.
  - `get_analytics_metrics()` computes 100% live KPIs from SQLite rows (conversion rate, avg score, Hot/Warm/Cold counts, sentiment counts, service demand, daily & ISO-weekly call counts).

### C. RAG Layer (`rag/`)
- **`rag/document_loader.py`**:
  - Reads `.txt`/`.md` from `knowledge_base/`.
  - Lazy-loads LangChain's `RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=80)` inside `chunk_documents()` (cutting FastAPI cold import time from ~59s to ~2.3s!).
  - Why `500` chars with `80` overlap? Small enough for focused semantic retrieval and low token usage; overlap prevents facts split across chunk boundaries (like pricing tiers + SLAs) from losing context.
- **`rag/embeddings.py`**:
  - Uses `SentenceTransformer("all-MiniLM-L6-v2")` (384 dimensions) with `local_files_only=True` first so cached models load offline instantly without HTTP timeout hangs.
  - Normalizes vectors (`normalize_embeddings=True`) so inner product equals cosine similarity.
  - Honest fallback: if `SentenceTransformer` cannot load, uses deterministic MD5 lexical + character-trigram signed hashing (`offline_hash_fallback`) and reports the mode transparently.
- **`rag/vector_store.py`**:
  - Uses `faiss.IndexFlatIP` (exact cosine similarity on L2-normalized embeddings) persisted to `data/faiss_index/index.faiss` + `chunks.json` + `vectors.npy`.
  - Lazy-loads `faiss` and provides a pure NumPy `vectors @ q_arr[0]` exact fallback if the Windows FAISS C++ DLL encounters handle errors.
- **`rag/retriever.py`**:
  - `retrieve_company_information(query, top_k=4, min_score=0.22)` enforces a similarity threshold. If no chunk passes `0.22`, returns `found: False` so the agent refuses to hallucinate.

### D. Voice Layer (`voice/`)
- **`voice/speech_to_text.py`**:
  - Lazy-loads `faster_whisper.WhisperModel("base", device="cpu", compute_type="int8")`.
  - Writes incoming audio bytes to a temporary file, runs `model.transcribe(..., beam_size=5, vad_filter=True)` (VAD removes silence to reduce hallucinated Whisper text and speed up decoding), and deletes the temp file in `finally`.
- **`voice/text_to_speech.py`**:
  - Uses Microsoft `edge_tts.Communicate` asynchronously to stream MP3 audio bytes in memory (no leftover disk `.mp3` clutter).
  - `_clean_for_speech()` strips `[Source: ...]` tags and markdown symbols (`*`, `#`, `` ` ``) so spoken replies sound natural.
  - `synthesize_sync()` safely handles running inside or outside an active asyncio event loop (`ThreadPoolExecutor` bridge if an event loop is already active).

### E. AI Engine (`ai_engine/`)
- **`ai_engine/llm.py`**:
  - Wraps `google.genai.Client` (`gemini-2.5-flash`).
  - Handles `429 / RESOURCE_EXHAUSTED` with exponential retry backoff.
  - If `GEMINI_API_KEY` is missing or the API fails, returns `mode="demo_fallback"` + `fallback_reason` so the UI always displays an honest badge instead of pretending simulated replies came from Gemini.
- **`ai_engine/memory.py`**:
  - `build_session_context(db, session_id)` fetches strictly messages for that `session_id` and the linked `Lead` profile — preventing cross-session data leakage.
  - `extract_customer_details()` uses Gemini JSON mode (primary) + regex/NLP fallback (`_regex_extract_customer_details`) and enforces **zero hallucination**: unmentioned fields stay `None` (`Unknown` in UI).
- **`ai_engine/lead_qualification.py`**:
  - Transparent 0–100 BANT rubric:
    - **Intent & Need Clarity (0–30 pts)**: Service interest (+10), clear requirement (+10), purchase intent High/Med (+7/+4), contact info (+3), negative sentiment (-4).
    - **Budget Readiness (0–25 pts)**: Growth/Enterprise budget (+25), Starter/numeric budget (+18).
    - **Timeline / Urgency (0–25 pts)**: Immediate/1 month (+25), 1–3 months (+18), 3–6 months (+12), exploratory (+5).
    - **Decision Authority (0–20 pts)**: C-level/VP/Founder/Director (+20), Manager/Evaluator (+13).
  - Tiers: **Hot** (≥ 70), **Warm** (40–69), **Cold** (< 40).
- **`ai_engine/sentiment.py`**:
  - Extracts `sentiment` (`Positive`/`Neutral`/`Negative`), `engagement`, `purchase_intent`, `urgency`, `customer_satisfaction`, and `objections` (Pricing, Data Privacy/Security, Integration Complexity, Timeline).
- **`ai_engine/agent.py`**:
  - Executes the 7-step per-turn pipeline in `process_turn()`:
    1. Sentiment & objection analysis
    2. Strict CRM entity extraction
    3. BANT lead qualification + SQLite update
    4. Conditional RAG knowledge retrieval (`_is_company_knowledge_query`)
    5. Appointment availability check & confirmation-gated booking (`_is_booking_intent` + `_is_explicit_confirmation`)
    6. Persist user turn telemetry to `Message`
    7. Generate grounded reply (Gemini or honest Demo Fallback) + persist assistant turn + `tool_events`

---

## 3. Common 3rd-Round Technical Interview Questions & Model Answers

### Q1: Why did you choose `IndexFlatIP` in FAISS instead of `IndexIVFFlat` or `HNSW`?
- Our company knowledge base has tens to a few thousand chunks. `IndexFlatIP` performs **exact** brute-force cosine similarity (on L2-normalized vectors) in sub-millisecond time with zero index-training overhead or recall loss. At 100k+ documents / multi-tenant scale, we would migrate to **HNSW** in Qdrant or `pgvector` for sub-linear approximate nearest neighbor search with metadata filtering per tenant.

### Q2: How do you stop the LLM from hallucinating pricing or booking fake appointments?
- **Two guardrails:**
  1. **RAG Thresholding + Prompt Grounding:** Chunks below cosine similarity `0.22` are dropped; when `found=False`, the system instruction forces the model to state it lacks sufficient knowledge-base data instead of guessing.
  2. **Deterministic Confirmation Gate in Code:** The LLM never writes directly to SQLite. Appointment creation is a Python tool (`book_appointment_record`) that checks `confirmed_by_customer=True`, validates name + email, and queries SQLite for conflicting `Confirmed` slots before committing.

### Q3: How does Faster-Whisper achieve fast CPU inference, and why Edge TTS?
- `Faster-Whisper` uses `CTranslate2` with `int8` quantization and Silero VAD (`vad_filter=True`), making CPU transcription ~4x faster and lower-memory than vanilla PyTorch Whisper without external API costs. `Edge TTS` provides high-naturalness neural voices (`en-US-AriaNeural`) over WebSocket with zero GPU requirement; if offline, our engine cleanly falls back to text display.

### Q4: How would you scale this MVP from 1 local user to 100,000 users?
- **Stateless Compute:** Containerize FastAPI and frontend pods in Kubernetes behind an ALB/NGINX ingress with Horizontal Pod Autoscaling.
- **Database:** Move from SQLite (single-writer file lock) to Managed **PostgreSQL** with `PgBouncer` connection pooling, read replicas for BI analytics, and `SELECT ... FOR UPDATE` / unique partial indexes on `(appointment_date, appointment_time) WHERE status = 'Confirmed'` to prevent race-condition double-bookings under high concurrency.
- **Session Memory & Caching:** Store active turn windows in **Redis Cluster** and cache frequent RAG FAQ answers semantically to cut LLM latency and cost by 40–60%.
- **Async Voice Workers:** Offload Whisper STT to dedicated **GPU worker pools** (T4/L4) via RabbitMQ/Celery queues or WebRTC streaming so API workers never block on audio decoding.

### Q5: How do you ensure customer data isolation and security?
- Every session has a unique `sp-<uuid>` ID linked to a single `Lead`, and `build_session_context()` strictly filters SQL queries by `session_id`.
- Secrets live only in `.env` (excluded via `.gitignore`), never in frontend code or API payloads.
- All REST endpoints validate inputs via Pydantic schemas; in production, we add JWT/OAuth2 RBAC, AES-256 encryption at rest, TLS 1.3 in transit, and PII redaction before external LLM calls.
