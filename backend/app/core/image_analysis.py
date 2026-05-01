"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  IGRIS IMAGE ANALYSIS ENGINE
  Upload image → Igris analyzes using GPT-4V / Gemini Vision / Claude
  Features: object detection, text extraction, scene analysis, Q&A
  No fake stubs — real LLM vision API calls
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

from __future__ import annotations

import asyncio
import base64
import json
import logging
import mimetypes
import os
import time
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional

import requests

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
#  DATA STRUCTURES
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class ImageAnalysisResult:
    analysis: str
    model_used: str
    provider: str
    image_size_bytes: int
    latency_ms: float
    success: bool = True
    error: Optional[str] = None
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        return asdict(self)


# ─────────────────────────────────────────────────────────────────────────────
#  VISION PROVIDERS
# ─────────────────────────────────────────────────────────────────────────────

class _OpenAIVision:
    """GPT-4o / GPT-4V vision via OpenAI API."""

    def __init__(self):
        self.api_key = os.getenv("OPENAI_API_KEY", "")
        self.model = "gpt-4o"

    @property
    def available(self) -> bool:
        return bool(self.api_key)

    async def analyze(
        self, image_b64: str, mime: str, prompt: str, max_tokens: int = 1000
    ) -> ImageAnalysisResult:
        t = time.time()
        try:
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            }
            payload = {
                "model": self.model,
                "max_tokens": max_tokens,
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:{mime};base64,{image_b64}",
                                    "detail": "high",
                                },
                            },
                        ],
                    }
                ],
            }
            resp = await asyncio.to_thread(
                requests.post,
                "https://api.openai.com/v1/chat/completions",
                headers=headers,
                json=payload,
                timeout=60,
            )
            if resp.status_code == 200:
                data = resp.json()
                text = data["choices"][0]["message"]["content"]
                return ImageAnalysisResult(
                    analysis=text,
                    model_used=self.model,
                    provider="openai",
                    image_size_bytes=len(image_b64) * 3 // 4,
                    latency_ms=(time.time() - t) * 1000,
                )
            else:
                return ImageAnalysisResult(
                    analysis="", model_used=self.model, provider="openai",
                    image_size_bytes=0, latency_ms=(time.time() - t) * 1000,
                    success=False, error=f"HTTP {resp.status_code}: {resp.text[:300]}",
                )
        except Exception as e:
            return ImageAnalysisResult(
                analysis="", model_used=self.model, provider="openai",
                image_size_bytes=0, latency_ms=(time.time() - t) * 1000,
                success=False, error=str(e),
            )


class _GeminiVision:
    """Gemini 2.0 Flash / 1.5 Pro vision via Google AI API."""

    def __init__(self):
        self.api_key = os.getenv("GEMINI_API_KEY", "") or os.getenv("GOOGLE_API_KEY", "")
        self.model = "gemini-2.0-flash"

    @property
    def available(self) -> bool:
        return bool(self.api_key)

    async def analyze(
        self, image_b64: str, mime: str, prompt: str, max_tokens: int = 1000
    ) -> ImageAnalysisResult:
        t = time.time()
        try:
            url = (
                f"https://generativelanguage.googleapis.com/v1beta/models/"
                f"{self.model}:generateContent?key={self.api_key}"
            )
            payload = {
                "contents": [
                    {
                        "parts": [
                            {"text": prompt},
                            {
                                "inline_data": {
                                    "mime_type": mime,
                                    "data": image_b64,
                                }
                            },
                        ]
                    }
                ],
                "generationConfig": {"maxOutputTokens": max_tokens},
            }
            resp = await asyncio.to_thread(
                requests.post, url, json=payload, timeout=60
            )
            if resp.status_code == 200:
                data = resp.json()
                text = data["candidates"][0]["content"]["parts"][0]["text"]
                return ImageAnalysisResult(
                    analysis=text,
                    model_used=self.model,
                    provider="gemini",
                    image_size_bytes=len(image_b64) * 3 // 4,
                    latency_ms=(time.time() - t) * 1000,
                )
            else:
                return ImageAnalysisResult(
                    analysis="", model_used=self.model, provider="gemini",
                    image_size_bytes=0, latency_ms=(time.time() - t) * 1000,
                    success=False, error=f"HTTP {resp.status_code}: {resp.text[:300]}",
                )
        except Exception as e:
            return ImageAnalysisResult(
                analysis="", model_used=self.model, provider="gemini",
                image_size_bytes=0, latency_ms=(time.time() - t) * 1000,
                success=False, error=str(e),
            )


class _AnthropicVision:
    """Claude 3.5 Sonnet / Opus vision via Anthropic API."""

    def __init__(self):
        self.api_key = os.getenv("ANTHROPIC_API_KEY", "")
        self.model = "claude-3-5-sonnet-20241022"

    @property
    def available(self) -> bool:
        return bool(self.api_key)

    async def analyze(
        self, image_b64: str, mime: str, prompt: str, max_tokens: int = 1000
    ) -> ImageAnalysisResult:
        t = time.time()
        try:
            headers = {
                "x-api-key": self.api_key,
                "anthropic-version": "2023-06-01",
                "Content-Type": "application/json",
            }
            # Claude expects media_type without charset
            media_type = mime.split(";")[0].strip()
            payload = {
                "model": self.model,
                "max_tokens": max_tokens,
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "image",
                                "source": {
                                    "type": "base64",
                                    "media_type": media_type,
                                    "data": image_b64,
                                },
                            },
                            {"type": "text", "text": prompt},
                        ],
                    }
                ],
            }
            resp = await asyncio.to_thread(
                requests.post,
                "https://api.anthropic.com/v1/messages",
                headers=headers,
                json=payload,
                timeout=60,
            )
            if resp.status_code == 200:
                data = resp.json()
                text = data["content"][0]["text"]
                return ImageAnalysisResult(
                    analysis=text,
                    model_used=self.model,
                    provider="anthropic",
                    image_size_bytes=len(image_b64) * 3 // 4,
                    latency_ms=(time.time() - t) * 1000,
                )
            else:
                return ImageAnalysisResult(
                    analysis="", model_used=self.model, provider="anthropic",
                    image_size_bytes=0, latency_ms=(time.time() - t) * 1000,
                    success=False, error=f"HTTP {resp.status_code}: {resp.text[:300]}",
                )
        except Exception as e:
            return ImageAnalysisResult(
                analysis="", model_used=self.model, provider="anthropic",
                image_size_bytes=0, latency_ms=(time.time() - t) * 1000,
                success=False, error=str(e),
            )


# ─────────────────────────────────────────────────────────────────────────────
#  MASTER IMAGE ANALYSIS ENGINE
# ─────────────────────────────────────────────────────────────────────────────

class IgrisImageAnalyzer:
    """
    Multi-provider image analysis engine.

    Priority: GPT-4o → Gemini 2.0 Flash → Claude 3.5 Sonnet
    Falls back automatically if one provider is unavailable.

    Usage:
    ──────
    result = await analyzer.analyze_file("/path/to/image.png", "What do you see?")
    result = await analyzer.analyze_bytes(image_bytes, "png", "Describe this")
    result = await analyzer.analyze_b64(b64_str, "image/png", "Extract text")
    """

    SUPPORTED_MIME = {
        "png": "image/png",
        "jpg": "image/jpeg",
        "jpeg": "image/jpeg",
        "gif": "image/gif",
        "webp": "image/webp",
        "bmp": "image/bmp",
    }

    DEFAULT_PROMPT = (
        "Analyze this image comprehensively. Describe:\n"
        "1. Main objects/subjects\n"
        "2. Text visible (OCR)\n"
        "3. Scene/environment\n"
        "4. Colors and composition\n"
        "5. Any notable details or anomalies\n"
        "Be specific and detailed."
    )

    def __init__(self) -> None:
        self._openai = _OpenAIVision()
        self._gemini = _GeminiVision()
        self._anthropic = _AnthropicVision()
        self._history: List[Dict[str, Any]] = []

        providers = []
        if self._openai.available:
            providers.append("openai")
        if self._gemini.available:
            providers.append("gemini")
        if self._anthropic.available:
            providers.append("anthropic")
        logger.info(f"[IMAGE] Vision engine online — providers: {providers or ['none']}")

    @property
    def available(self) -> bool:
        return self._openai.available or self._gemini.available or self._anthropic.available

    def _detect_mime(self, filename: str) -> str:
        ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
        return self.SUPPORTED_MIME.get(ext, "image/png")

    async def analyze_b64(
        self,
        image_b64: str,
        mime: str = "image/png",
        prompt: Optional[str] = None,
        provider: Optional[str] = None,
        max_tokens: int = 1000,
    ) -> ImageAnalysisResult:
        """Analyze a base64-encoded image."""
        prompt = prompt or self.DEFAULT_PROMPT

        # Provider selection
        providers = []
        if provider:
            if provider == "openai" and self._openai.available:
                providers = [self._openai]
            elif provider == "gemini" and self._gemini.available:
                providers = [self._gemini]
            elif provider == "anthropic" and self._anthropic.available:
                providers = [self._anthropic]
        if not providers:
            # Auto fallback order
            if self._openai.available:
                providers.append(self._openai)
            if self._gemini.available:
                providers.append(self._gemini)
            if self._anthropic.available:
                providers.append(self._anthropic)

        if not providers:
            return ImageAnalysisResult(
                analysis="", model_used="none", provider="none",
                image_size_bytes=0, latency_ms=0,
                success=False,
                error="No vision provider available. Set OPENAI_API_KEY, GEMINI_API_KEY, or ANTHROPIC_API_KEY.",
            )

        # Try each provider with fallback
        for p in providers:
            result = await p.analyze(image_b64, mime, prompt, max_tokens)
            if result.success:
                self._history.append({
                    "provider": result.provider,
                    "model": result.model_used,
                    "prompt": prompt[:100],
                    "latency_ms": result.latency_ms,
                    "ts": time.time(),
                })
                return result
            logger.warning(f"[IMAGE] {result.provider} failed: {result.error}")

        # All failed — return last error
        return result  # type: ignore[possibly-undefined]

    async def analyze_bytes(
        self,
        image_bytes: bytes,
        ext: str = "png",
        prompt: Optional[str] = None,
        provider: Optional[str] = None,
    ) -> ImageAnalysisResult:
        """Analyze raw image bytes."""
        b64 = base64.b64encode(image_bytes).decode("utf-8")
        mime = self.SUPPORTED_MIME.get(ext.lower().strip("."), "image/png")
        return await self.analyze_b64(b64, mime, prompt, provider)

    async def analyze_file(
        self,
        file_path: str,
        prompt: Optional[str] = None,
        provider: Optional[str] = None,
    ) -> ImageAnalysisResult:
        """Analyze an image file from disk."""
        file_path = os.path.abspath(file_path)
        if not os.path.isfile(file_path):
            return ImageAnalysisResult(
                analysis="", model_used="", provider="",
                image_size_bytes=0, latency_ms=0,
                success=False, error=f"File not found: {file_path}",
            )
        with open(file_path, "rb") as f:
            data = f.read()
        mime = self._detect_mime(file_path)
        return await self.analyze_bytes(data, mime.split("/")[-1], prompt, provider)

    async def compare_images(
        self,
        image1_b64: str,
        image2_b64: str,
        mime: str = "image/png",
        prompt: Optional[str] = None,
    ) -> ImageAnalysisResult:
        """Compare two images (works with OpenAI multi-image support)."""
        prompt = prompt or "Compare these two images. Describe the differences and similarities."
        if self._openai.available:
            t = time.time()
            try:
                headers = {
                    "Authorization": f"Bearer {self._openai.api_key}",
                    "Content-Type": "application/json",
                }
                payload = {
                    "model": self._openai.model,
                    "max_tokens": 1500,
                    "messages": [
                        {
                            "role": "user",
                            "content": [
                                {"type": "text", "text": prompt},
                                {
                                    "type": "image_url",
                                    "image_url": {"url": f"data:{mime};base64,{image1_b64}"},
                                },
                                {
                                    "type": "image_url",
                                    "image_url": {"url": f"data:{mime};base64,{image2_b64}"},
                                },
                            ],
                        }
                    ],
                }
                resp = await asyncio.to_thread(
                    requests.post,
                    "https://api.openai.com/v1/chat/completions",
                    headers=headers, json=payload, timeout=60,
                )
                if resp.status_code == 200:
                    text = resp.json()["choices"][0]["message"]["content"]
                    return ImageAnalysisResult(
                        analysis=text, model_used=self._openai.model,
                        provider="openai",
                        image_size_bytes=(len(image1_b64) + len(image2_b64)) * 3 // 4,
                        latency_ms=(time.time() - t) * 1000,
                    )
            except Exception as e:
                pass

        # Fallback: analyze separately
        r1 = await self.analyze_b64(image1_b64, mime, "Describe this image (Image 1)")
        r2 = await self.analyze_b64(image2_b64, mime, "Describe this image (Image 2)")
        combined = f"Image 1:\n{r1.analysis}\n\nImage 2:\n{r2.analysis}"
        return ImageAnalysisResult(
            analysis=combined, model_used=r1.model_used,
            provider=r1.provider, image_size_bytes=r1.image_size_bytes + r2.image_size_bytes,
            latency_ms=r1.latency_ms + r2.latency_ms,
        )

    async def extract_text(self, image_b64: str, mime: str = "image/png") -> str:
        """OCR — extract text from image."""
        result = await self.analyze_b64(
            image_b64, mime,
            "Extract ALL text visible in this image. Return only the text, nothing else. "
            "Preserve formatting and line breaks."
        )
        return result.analysis if result.success else f"OCR failed: {result.error}"

    def get_history(self, limit: int = 20) -> List[Dict[str, Any]]:
        return self._history[-limit:]

    def get_status(self) -> Dict[str, Any]:
        return {
            "available": self.available,
            "providers": {
                "openai_gpt4o": self._openai.available,
                "gemini_flash": self._gemini.available,
                "anthropic_claude": self._anthropic.available,
            },
            "total_analyses": len(self._history),
        }


# ─────────────────────────────────────────────────────────────────────────────
#  SINGLETON
# ─────────────────────────────────────────────────────────────────────────────

_instance: Optional[IgrisImageAnalyzer] = None


def get_image_analyzer() -> IgrisImageAnalyzer:
    global _instance
    if _instance is None:
        _instance = IgrisImageAnalyzer()
    return _instance
