# SalesPilot AI — One-Page Executive Project Report

**Organization Simulation:** TechNova Solutions | **Project:** Autonomous AI Sales Voice Agent MVP

---

## 1. Business Problem
Inbound B2B sales teams face three chronic bottlenecks: slow response times outside business hours, inconsistent lead qualification across representatives, and incomplete CRM hygiene after discovery calls. Prospects asking technical pricing or integration questions often abandon funnels before speaking to a Solutions Architect.

## 2. Proposed Solution
**SalesPilot AI** is an autonomous, voice-first AI sales representative that engages prospects 24/7 over browser voice or text, answers company-specific questions accurately using Retrieval-Augmented Generation (RAG), qualifies leads transparently using BANT criteria, tracks live customer sentiment and objections, books confirmed consultations without double-booking, and logs structured call summaries directly into a CRM.

## 3. Technical Architecture
The system follows a clean five-layer modular architecture:
- **Frontend:** Multi-page Streamlit SaaS workspace (8 operational views with dark-navy/white theme & animated voice waveform).
- **Backend API:** FastAPI REST layer with Pydantic validation, dependency-injected SQLAlchemy sessions, and `/health` telemetry.
- **Voice Layer:** Local **Faster-Whisper** (`int8` CPU) for Speech-to-Text and **Edge TTS** (`en-US-AriaNeural`) for natural neural Text-to-Speech.
- **AI & RAG Layer:** Google **Gemini API** (`gemini-2.5-flash`) orchestrated by `SalesPilotAgent` alongside **LangChain** chunking, **SentenceTransformers** (`all-MiniLM-L6-v2`), and **FAISS** cosine vector search, plus an honest transparent `Demo Fallback Mode` when no API key is present.
- **Data Layer:** **SQLite** relational persistence for Leads, Isolated Call Sessions, Turn Transcripts, Appointments, and Call Summaries, visualized in **Plotly**.

## 4. Key AI Capabilities
- **Grounded RAG with Anti-Hallucination Guard:** Every company answer cites exact source files (`pricing.txt`, `services.txt`, etc.). Queries falling below the similarity threshold trigger an explicit "insufficient information" disclosure.
- **Transparent BANT Lead Qualification (0–100):** Scores Intent/Need (30), Budget (25), Timeline (25), and Decision Authority (20), classifying leads as **Hot** (70+), **Warm** (40–69), or **Cold** (<40) with full score reasoning and zero fabricated fields.
- **Turn-by-Turn Sentiment & Objection Telemetry:** Tracks Positive/Neutral/Negative sentiment, engagement, purchase intent, urgency, and objections (Pricing, Security, Integration, Timeline).
- **Confirmation-Gated Appointment Tool:** Checks slot availability and enforces explicit customer confirmation + name/email validation + SQLite conflict prevention.

## 5. Implementation & Verification
The MVP is organized into isolated packages (`backend/`, `frontend/`, `ai_engine/`, `rag/`, `voice/`, `crm/`, `knowledge_base/`, `tests/`) and verified by an automated `pytest` suite covering lead scoring, RAG retrieval & negative hallucination checks, session isolation, double-booking prevention, call summarization, and the complete end-to-end API workflow.

## 6. Business Value
- **Zero-Wait Lead Response:** Instant voice engagement and technical Q&A 24/7.
- **Standardized Qualification:** Eliminates manual CRM data entry and subjective lead scoring.
- **Higher Architect Utilization:** Solutions Architects receive pre-qualified leads with booked demos and executive call briefs.

## 7. Scalability & Future Enhancements
- **Scaling to 100,000 Users:** Transition to stateless Dockerized Kubernetes pods, Redis distributed session memory, PostgreSQL with read replicas, Qdrant/pgvector distributed search, and async GPU worker queues for Whisper STT.
- **Future Enhancements:** Twilio/SIP PSTN telephony integration, bidirectional HubSpot/Salesforce sync, multilingual voice switching, and real-time WebRTC full-duplex barge-in audio streaming.
