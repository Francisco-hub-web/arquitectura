"""Cliente mínimo de Ollama (API REST local) sin dependencias. Los datos nunca salen de la máquina."""
from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from typing import Any, Dict, List, Optional, Tuple

THINK = re.compile(r"<think>.*?</think>", re.DOTALL)


def _host() -> str:
    h = os.environ.get("OLLAMA_HOST", "http://localhost:11434").strip()
    if not h.startswith(("http://", "https://")):
        h = "http://" + h
    return h.replace("0.0.0.0", "localhost").rstrip("/")


class OllamaError(RuntimeError):
    pass


class Ollama:
    def __init__(self, model: Optional[str] = None, host: Optional[str] = None, timeout: int = 600):
        self.model = model or os.environ.get("GOVKIT_MODEL", "qwen2.5:7b-instruct")
        self.host = (host or _host()).rstrip("/")
        self.timeout = timeout

    def _req(self, path: str, payload: Optional[Dict[str, Any]] = None, timeout: Optional[int] = None) -> Dict[str, Any]:
        data = json.dumps(payload).encode("utf-8") if payload is not None else None
        req = urllib.request.Request(self.host + path, data=data, method="POST" if data else "GET",
                                     headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=timeout or self.timeout) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", "ignore")[:300]
            raise OllamaError(f"HTTP {exc.code}: {body}") from exc
        except (urllib.error.URLError, OSError) as exc:
            raise OllamaError(f"no se pudo conectar a {self.host}: {exc}") from exc

    def health(self) -> Tuple[bool, str]:
        try:
            v = self._req("/api/version", timeout=3)
            return True, f"Ollama {v.get('version', '?')} disponible"
        except OllamaError as exc:
            return False, str(exc)

    def models(self) -> List[str]:
        try:
            return [m.get("name", "") for m in self._req("/api/tags", timeout=5).get("models", [])]
        except OllamaError:
            return []

    def chat(self, messages: List[Dict[str, str]], schema: Optional[Dict[str, Any]] = None, num_ctx: int = 8192,
             temperature: float = 0.0) -> str:
        """Llamada determinista (temperature 0, seed fija). `schema` activa structured outputs (Ollama ≥0.5);
        si el servidor no lo soporta, se degrada a format=json."""
        payload: Dict[str, Any] = {"model": self.model, "messages": messages, "stream": False,
                                   "options": {"temperature": temperature, "num_ctx": num_ctx, "seed": 42}}
        if schema is not None:
            payload["format"] = schema
        try:
            out = self._req("/api/chat", payload)
        except OllamaError as exc:
            if schema is not None and "format" in str(exc).lower():
                payload["format"] = "json"
                out = self._req("/api/chat", payload)
            else:
                raise
        content = (out.get("message") or {}).get("content", "")
        return THINK.sub("", content).strip()
