"""HTTP API client connecting the Streamlit UI to the FastAPI backend."""

from typing import Any, Dict, Optional
import httpx

from backend.config import settings


class BackendClient:
    """Thin wrapper over FastAPI REST endpoints."""

    def __init__(self, base_url: Optional[str] = None) -> None:
        self.base_url = (base_url or settings.backend_url).rstrip("/")

    def _request(self, method: str, path: str, timeout: float = 45.0, **kwargs: Any) -> Any:
        url = f"{self.base_url}{path}"
        with httpx.Client(timeout=timeout) as client:
            resp = client.request(method, url, **kwargs)
            resp.raise_for_status()
            return resp.json()

    def health(self) -> Optional[Dict[str, Any]]:
        try:
            return self._request("GET", "/health", timeout=3.0)
        except Exception:
            return None

    # Sessions & Agent
    def start_session(self, mode: str = "voice", include_audio: bool = True) -> Dict[str, Any]:
        return self._request(
            "POST",
            "/api/sessions",
            json={"mode": mode, "include_audio": include_audio},
        )

    def list_sessions(self) -> Dict[str, Any]:
        return self._request("GET", "/api/sessions")

    def get_session(self, session_id: str) -> Dict[str, Any]:
        return self._request("GET", f"/api/sessions/{session_id}")

    def send_chat(self, session_id: str, message: str, include_audio: bool = True) -> Dict[str, Any]:
        return self._request(
            "POST",
            f"/api/sessions/{session_id}/chat",
            timeout=60.0,
            json={"message": message, "include_audio": include_audio},
        )

    def send_voice(
        self,
        session_id: str,
        audio_bytes: bytes,
        filename: str = "recording.wav",
        include_audio: bool = True,
    ) -> Dict[str, Any]:
        return self._request(
            "POST",
            f"/api/sessions/{session_id}/voice",
            timeout=90.0,
            files={"audio": (filename, audio_bytes, "audio/wav")},
            data={"include_audio": str(include_audio).lower()},
        )

    def end_session(self, session_id: str) -> Dict[str, Any]:
        return self._request("POST", f"/api/sessions/{session_id}/end", timeout=45.0)

    # CRM Leads
    def list_leads(
        self,
        query: Optional[str] = None,
        category: Optional[str] = None,
        status: Optional[str] = None,
    ) -> Dict[str, Any]:
        params = {}
        if query:
            params["q"] = query
        if category and category != "All":
            params["category"] = category
        if status and status != "All":
            params["status"] = status
        return self._request("GET", "/api/leads", params=params)

    def get_lead_detail(self, lead_id: int) -> Dict[str, Any]:
        return self._request("GET", f"/api/leads/{lead_id}")

    def update_lead(self, lead_id: int, updates: Dict[str, Any]) -> Dict[str, Any]:
        return self._request("PATCH", f"/api/leads/{lead_id}", json=updates)

    def delete_lead(self, lead_id: int) -> Dict[str, Any]:
        return self._request("DELETE", f"/api/leads/{lead_id}")

    # Appointments
    def list_appointments(self, status: Optional[str] = None) -> Dict[str, Any]:
        params = {"status": status} if status and status != "All" else {}
        return self._request("GET", "/api/appointments", params=params)

    def check_availability(self, date_str: str) -> Dict[str, Any]:
        return self._request("GET", "/api/appointments/availability", params={"date": date_str})

    def book_appointment(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        return self._request("POST", "/api/appointments", json=payload)

    def cancel_appointment(self, appointment_id: int) -> Dict[str, Any]:
        return self._request("POST", f"/api/appointments/{appointment_id}/cancel")

    # Knowledge Base
    def list_knowledge(self) -> Dict[str, Any]:
        return self._request("GET", "/api/knowledge")

    def add_knowledge(self, filename: str, content: str) -> Dict[str, Any]:
        return self._request("POST", "/api/knowledge", json={"filename": filename, "content": content})

    def query_knowledge(self, query: str, top_k: int = 4) -> Dict[str, Any]:
        return self._request("POST", "/api/knowledge/query", json={"query": query, "top_k": top_k})

    # Analytics & Summaries & Settings
    def get_analytics(self) -> Dict[str, Any]:
        return self._request("GET", "/api/analytics")

    def list_summaries(self) -> Dict[str, Any]:
        return self._request("GET", "/api/calls/summaries")

    def update_config(self, gemini_api_key: Optional[str] = None, edge_tts_voice: Optional[str] = None) -> Dict[str, Any]:
        return self._request(
            "POST",
            "/api/settings/config",
            json={"gemini_api_key": gemini_api_key, "edge_tts_voice": edge_tts_voice},
        )


api_client = BackendClient()
