"""
Direct REST client for Google Gemini API via httpx.
Communicates directly with https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent
Provides bounded retries, fine-grained timeouts, structured tool parsing, and error classification.
Zero unverified external SDK dependencies.
"""
from typing import Dict, Any, List, Optional
import time
import random
import logging
import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)


class GeminiError(Exception):
    """Base exception for Gemini API operations."""
    pass


class GeminiAuthError(GeminiError):
    """Authentication or permission failure (HTTP 401/403)."""
    pass


class GeminiQuotaError(GeminiError):
    """Quota exhausted or rate limited (HTTP 429)."""
    pass


class GeminiTimeoutError(GeminiError):
    """Connection or read timeout."""
    pass


class GeminiServiceError(GeminiError):
    """Google Generative Language API server error (HTTP 5xx)."""
    pass


class GeminiBadRequestError(GeminiError):
    """Malformed request payload (HTTP 400)."""
    pass


class GeminiRESTClient:
    """
    Direct REST API client for Google Gemini models.
    Default model: gemini-3.8-flash (configurable via settings.GEMINI_MODEL).
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        timeout: float = 15.0,
        connect_timeout: float = 5.0,
        max_retries: int = 2,
    ):
        self.api_key = api_key if api_key is not None else settings.GEMINI_API_KEY
        self.model = model or settings.GEMINI_MODEL
        self.timeout = httpx.Timeout(timeout, connect=connect_timeout)
        self.max_retries = max_retries
        self.base_url = "https://generativelanguage.googleapis.com/v1beta/models"

    def is_configured(self) -> bool:
        """Check if API key is provided and not a placeholder."""
        if not self.api_key or not self.api_key.strip():
            return False
        key_lower = self.api_key.lower().strip()
        placeholders = {"placeholder", "change-me", "your-api-key", "default", "test-key"}
        return not any(p in key_lower for p in placeholders)

    def generate_content(
        self,
        contents: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
        system_instruction: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Invoke Gemini generateContent via HTTP POST with bounded retries.
        Returns parsed text and function calls.
        """
        if not self.is_configured():
            raise GeminiAuthError("GEMINI_API_KEY is not configured or is a placeholder.")

        endpoint = f"{self.base_url}/{self.model}:generateContent"
        headers = {
            "x-goog-api-key": self.api_key,
            "Content-Type": "application/json",
        }

        payload: Dict[str, Any] = {
            "contents": contents,
            "generationConfig": {
                "temperature": 0.2,
                "maxOutputTokens": 2048,
            },
        }

        if system_instruction:
            payload["systemInstruction"] = {
                "role": "system",
                "parts": [{"text": system_instruction}],
            }

        if tools:
            payload["tools"] = [{"functionDeclarations": tools}]

        last_error = None
        for attempt in range(self.max_retries + 1):
            try:
                with httpx.Client(timeout=self.timeout) as client:
                    response = client.post(endpoint, json=payload, headers=headers)

                status = response.status_code
                if status == 200:
                    return self._parse_response(response.json())

                if status in (401, 403):
                    raise GeminiAuthError(f"Gemini API authentication failed (HTTP {status}). Check GEMINI_API_KEY.")

                if status == 400:
                    err_msg = response.text[:500]
                    raise GeminiBadRequestError(f"Gemini API rejected request (HTTP 400): {err_msg}")

                if status == 429:
                    if attempt < self.max_retries:
                        sleep_time = (2 ** attempt) + random.uniform(0.1, 0.5)
                        logger.warning(f"Gemini API rate limited (429). Retrying in {sleep_time:.2f}s...")
                        time.sleep(sleep_time)
                        continue
                    raise GeminiQuotaError("Gemini API rate limit / quota exceeded (HTTP 429).")

                if 500 <= status < 600:
                    if attempt < 1:  # retry 5xx once
                        time.sleep(1.0)
                        continue
                    raise GeminiServiceError(f"Gemini API server error (HTTP {status}): {response.text[:200]}")

                raise GeminiError(f"Unexpected Gemini API response HTTP {status}: {response.text[:200]}")

            except httpx.TimeoutException as e:
                last_error = e
                if attempt < 1:
                    time.sleep(1.0)
                    continue
                raise GeminiTimeoutError(f"Connection/read timeout contacting Gemini API: {e}") from e
            except (GeminiError, httpx.RequestError) as e:
                last_error = e
                if isinstance(e, (GeminiAuthError, GeminiBadRequestError)):
                    raise
                if attempt >= self.max_retries:
                    raise

        raise GeminiError(f"Gemini API request failed after {self.max_retries} retries: {last_error}")

    def _parse_response(self, resp_json: Dict[str, Any]) -> Dict[str, Any]:
        """Parse Gemini generateContent JSON response into text and function calls."""
        candidates = resp_json.get("candidates", [])
        if not candidates:
            return {"text": "", "function_calls": [], "raw": resp_json}

        first_candidate = candidates[0]
        content = first_candidate.get("content", {})
        parts = content.get("parts", [])

        text_parts: List[str] = []
        function_calls: List[Dict[str, Any]] = []

        for p in parts:
            if "text" in p:
                text_parts.append(p["text"])
            if "functionCall" in p:
                fc = p["functionCall"]
                function_calls.append({
                    "name": fc.get("name", ""),
                    "args": fc.get("args", {}),
                })

        return {
            "text": "\n".join(text_parts).strip(),
            "function_calls": function_calls,
            "raw": resp_json,
        }
