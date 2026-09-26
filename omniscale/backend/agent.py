"""
backend/agent.py
OmniScale Enterprise Pro — Designed and Developed by NIKHIL CHARY SRIRAMOJU

Autonomous agent orchestration loop. A lightweight ReAct-style router
inspects the user's request, decides whether it needs document context
(RAG), image reasoning (CNN — via a pre-computed job result), or a direct
chat completion, then dispatches to the resolved LLM provider (Groq or
Gemini, chosen dynamically from whichever API key is configured).
"""
from __future__ import annotations

import logging
import time
from typing import Optional

from backend.config import LLMProvider, get_settings
from backend.rag_engine import retrieve

logger = logging.getLogger("omniscale.agent")
settings = get_settings()

_ROUTING_SYSTEM_PROMPT = (
    "You are OmniScale's routing classifier. Given a user request, reply with "
    "exactly one word: 'rag' if it references uploaded documents, files, or asks "
    "to look something up in provided context; 'cnn' if it is about analyzing, "
    "classifying, or describing an image; otherwise 'chat'. Reply with only that "
    "single word, nothing else."
)


class LLMClient:
    """Thin, provider-agnostic wrapper so the rest of the app never imports
    the Groq/Gemini SDKs directly."""

    def __init__(self) -> None:
        self.provider = settings.active_llm_provider
        if self.provider is LLMProvider.GROQ:
            from groq import Groq

            self._client = Groq(api_key=settings.GROQ_API_KEY)
        elif self.provider is LLMProvider.GEMINI:
            import google.generativeai as genai

            genai.configure(api_key=settings.GEMINI_API_KEY)
            self._client = genai.GenerativeModel(settings.GEMINI_MODEL)
        else:
            self._client = None
            logger.warning("No LLM provider configured — set GROQ_API_KEY or GEMINI_API_KEY")

    def complete(self, system_prompt: str, user_prompt: str, max_tokens: int = 1024) -> str:
        if self.provider is LLMProvider.GROQ:
            resp = self._client.chat.completions.create(
                model=settings.GROQ_MODEL,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                max_tokens=max_tokens,
                temperature=0.3,
            )
            return resp.choices[0].message.content or ""

        if self.provider is LLMProvider.GEMINI:
            resp = self._client.generate_content(f"{system_prompt}\n\n{user_prompt}")
            return resp.text or ""

        raise RuntimeError(
            "No LLM provider configured. Set GROQ_API_KEY or GEMINI_API_KEY in your environment."
        )


_client: Optional[LLMClient] = None


def get_llm_client() -> LLMClient:
    global _client
    if _client is None:
        _client = LLMClient()
    return _client


def _classify_route(prompt: str, force_route: Optional[str]) -> str:
    if force_route:
        return force_route
    client = get_llm_client()
    try:
        route = client.complete(_ROUTING_SYSTEM_PROMPT, prompt, max_tokens=5).strip().lower()
        if route in ("rag", "cnn", "chat"):
            return route
    except Exception as exc:  # noqa: BLE001
        logger.warning("Routing classification failed, defaulting to chat: %s", exc)
    return "chat"


def run_agent(prompt: str, namespace: Optional[str], force_route: Optional[str] = None) -> dict:
    """
    The autonomous agent loop:
      1. Classify the request into rag / cnn / chat.
      2. For 'rag', retrieve top-K chunks from the user's vector namespace
         and ground the answer in them.
      3. For 'cnn', instruct the caller that image analysis is dispatched
         asynchronously (the actual inference runs via Celery + cnn_module).
      4. For 'chat', answer directly.
    """
    start = time.perf_counter()
    route = _classify_route(prompt, force_route)
    client = get_llm_client()
    sources: list[str] = []

    if route == "rag":
        if not namespace:
            answer = "No document namespace was provided, so I can't search your uploaded files."
        else:
            chunks = retrieve(namespace, prompt, top_k=5)
            if not chunks:
                answer = "I couldn't find relevant content in your uploaded documents for that question."
            else:
                context = "\n\n".join(f"[{c.source_document}] {c.chunk_text}" for c in chunks)
                sources = sorted({c.source_document for c in chunks})
                system = (
                    "Answer the user's question using ONLY the provided context. "
                    "If the context is insufficient, say so explicitly."
                )
                answer = client.complete(system, f"Context:\n{context}\n\nQuestion: {prompt}")

    elif route == "cnn":
        answer = (
            "Image analysis requests are processed asynchronously by the CNN "
            "pipeline. Upload the image via /api/v1/cnn/analyze and poll the "
            "returned job id for results."
        )

    else:
        answer = client.complete(
            "You are OmniScale's helpful, precise enterprise assistant.", prompt
        )

    latency_ms = round((time.perf_counter() - start) * 1000, 2)
    return {
        "route_taken": route,
        "answer": answer,
        "provider": client.provider.value,
        "sources": sources,
        "latency_ms": latency_ms,
    }
