# SalesPilot AI — Autonomous AI Sales Voice Agent

**SalesPilot AI** is an industry-quality MVP of an autonomous AI sales voice representative built for **TechNova Solutions** (AI Automation, Cloud Services, Custom Software Development, and Business Intelligence).

It combines **FastAPI**, **Streamlit**, **Google Gemini API**, **Faster-Whisper (STT)**, **Edge TTS**, **LangChain + SentenceTransformers + FAISS (RAG)**, **SQLite CRM**, and **Plotly Analytics** in a modular, Windows-ready architecture.

---

## Key Features

- **Voice & Text Sales Conversations:** Record directly from the browser microphone (`st.audio_input`), transcribe locally via **Faster-Whisper**, generate grounded responses, and synthesize natural speech via **Edge TTS** — with a seamless text chat fallback.
- **Honest Fallback Modes:** Clearly displays `Live Gemini AI` vs `Demo Fallback Mode` in the UI and API responses whenever `GEMINI_API_KEY` is absent or rate-limited — never pretending simulated responses are live LLM calls.
- **Grounded RAG Pipeline:** Loads `knowledge_base/*.txt`, splits via LangChain `RecursiveCharacterTextSplitter`, embeds via `all-MiniLM-L6-v2`, indexes in **FAISS**, cites sources (`[Source: pricing.txt]`), and refuses to hallucinate when answers are missing from the knowledge base.
- **Session-Isolated Contextual Memory:** Maintains isolated per-session history and customer profiles in SQLite without cross-customer leakage.
- **Transparent BANT Lead Qualification (0–100):** Scores Intent/Need (30), Budget (25), Timeline (25), and Decision Authority (20) into **Hot / Warm / Cold** with explicit reasoning and `null`/`Unknown` for missing fields.
- **Real-Time Sentiment & Objection Tracking:** Tracks Positive/Neutral/Negative sentiment, engagement, purchase intent, urgency, and objections across conversation turns.
- **Confirmation-Gated Appointment Booking:** Checks slot availability, requires explicit customer confirmation + name/email, prevents double booking in SQLite, and supports cancellation.
- **8-Page SaaS Dashboard:** Overview, Live AI Sales Agent (with animated waveform & live CRM telemetry), CRM/Lead Management, Knowledge Base Inspector, Appointment Management, Call History & Summaries, Plotly Business Intelligence Analytics, and Settings.

---

## Project Structure

```text
salespilot-ai/
├── app.py                     # Streamlit 8-page SaaS UI entrypoint
├── backend/
│   ├── config.py              # Pydantic settings (.env)
│   ├── main.py                # FastAPI entrypoint & lifespan init
│   ├── routes/api.py          # REST API endpoints
│   └── schemas/api_schemas.py # Request/response validation models
├── frontend/                  # 8 UI pages + API client + CSS waveform theme
├── ai_engine/                 # Agent orchestrator, Gemini LLM client, memory, BANT, sentiment, summarizer
├── rag/                       # Document loader, SentenceTransformers embeddings, FAISS store, retriever
├── voice/                     # Faster-Whisper STT & Edge TTS engines
├── crm/                       # SQLite ORM models & CRUD + analytics queries
├── knowledge_base/            # TechNova Solutions domain documents
├── tests/                     # Unit & end-to-end API workflow tests
├── docs/                      # Architecture docs, PNG diagram, and 1-page report
├── .env.example
├── Dockerfile
└── requirements.txt
```

---

## Installation & Running on Windows (CMD)

### 1. Navigate to the project directory
```cmd
cd C:\Users\vvais\.gemini\antigravity\scratch\salespilot-ai
```

### 2. Create and activate a virtual environment (optional if packages are already installed globally)
```cmd
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

### 3. Configure environment variables
```cmd
copy .env.example .env
```
Open `.env` and add your Google Gemini API key:
```ini
GEMINI_API_KEY=your_actual_gemini_api_key_here
GEMINI_MODEL=gemini-2.5-flash
```
> **Note:** If `GEMINI_API_KEY` is left blank, SalesPilot AI runs cleanly in **Demo Fallback Mode** and displays a clear warning banner in the UI.

### 4. Start the FastAPI Backend (Terminal 1)
```cmd
uvicorn backend.main:app --host 127.0.0.1 --port 8000
```
Interactive Swagger API docs are available at `http://127.0.0.1:8000/docs`.

### 5. Start the Streamlit Frontend (Terminal 2)
```cmd
streamlit run app.py --server.port 8501
```
Open your browser at `http://localhost:8501`.

---

## Running Tests

```cmd
pytest -v
```

---

## API Documentation Summary

| Method | Endpoint | Purpose |
|---|---|---|
| `GET` | `/health` | System readiness, active LLM mode, embedding mode, KB chunk count |
| `POST` | `/api/sessions` | Start isolated voice/chat session & return greeting |
| `POST` | `/api/sessions/{id}/chat` | Process text turn through agent + RAG + CRM + optional TTS |
| `POST` | `/api/sessions/{id}/voice` | Transcribe audio via Faster-Whisper & process agent turn |
| `POST` | `/api/sessions/{id}/end` | Generate & persist structured Call Summary to CRM |
| `GET/PATCH/DELETE` | `/api/leads` | Search, filter, inspect, update, and delete CRM leads |
| `GET/POST` | `/api/appointments` | Check availability, book (with confirmation & conflict guard), cancel |
| `GET/POST` | `/api/knowledge` | List KB docs, add new docs & rebuild FAISS, run semantic search |
| `GET` | `/api/analytics` | Live SQLite KPIs, lead/sentiment distributions, daily/weekly activity |

---

## Documentation & Architecture

- Detailed Architecture & 100k-User Scalability Plan: [`docs/architecture.md`](docs/architecture.md)
- One-Page Executive Report: [`docs/PROJECT_REPORT.md`](docs/PROJECT_REPORT.md)
- System Architecture Diagram: [`docs/system_architecture.png`](docs/system_architecture.png)

## Data Security & Privacy Approach
- Secrets loaded exclusively via `.env` / environment variables; never exposed in frontend or committed to Git.
- Strict SQLite session isolation (`session_id` foreign-key scoping) prevents cross-customer context leakage.
- Pydantic schema validation on all REST inputs and explicit confirmation + conflict checks before database appointment writes.
