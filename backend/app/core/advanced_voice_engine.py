"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  IGRIS ADVANCED VOICE ENGINE
  STT: OpenAI Whisper (local) OR Google Web Speech API fallback
  TTS: ElevenLabs (cloud) OR pyttsx3 (local) fallback
  Features: wake-word, real-time transcription, voice cloning support
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

from __future__ import annotations

import asyncio
import base64
import io
import logging
import os
import queue
import tempfile
import threading
import time
from dataclasses import dataclass, field, asdict
from typing import Any, Callable, Dict, List, Optional

import requests

logger = logging.getLogger(__name__)

# ── Optional: Whisper (local, no API key) ────────────────────────────────────
try:
    import whisper as openai_whisper
    _WHISPER = True
    logger.info("[VOICE] Whisper STT available.")
except ImportError:
    _WHISPER = False
    logger.warning("[VOICE] Whisper not installed. Run: pip install openai-whisper")

# ── Optional: SpeechRecognition (fallback STT) ───────────────────────────────
try:
    import speech_recognition as sr
    _SR = True
except ImportError:
    _SR = False

# ── Optional: PyAudio for microphone input ───────────────────────────────────
try:
    import pyaudio
    _PYAUDIO = True
except ImportError:
    _PYAUDIO = False
    logger.warning("[VOICE] PyAudio not installed. Run: pip install pyaudio")

# ── Optional: sounddevice (alternative to PyAudio) ───────────────────────────
try:
    import sounddevice as sd
    import numpy as np
    _SOUNDDEVICE = True
except ImportError:
    _SOUNDDEVICE = False

# ── pyttsx3 fallback TTS ─────────────────────────────────────────────────────
try:
    import pyttsx3
    _PYTTSX3 = True
except ImportError:
    _PYTTSX3 = False


# ─────────────────────────────────────────────────────────────────────────────
#  DATA STRUCTURES
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class TranscriptionResult:
    text: str
    language: str
    confidence: float
    duration_ms: float
    engine: str  # "whisper" | "google" | "azure"
    timestamp: float = field(default_factory=time.time)
    success: bool = True
    error: Optional[str] = None

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class TTSResult:
    text: str
    engine: str  # "elevenlabs" | "openai_tts" | "pyttsx3"
    audio_b64: Optional[str]  # base64 audio for streaming to frontend
    duration_ms: float
    success: bool = True
    error: Optional[str] = None


# ─────────────────────────────────────────────────────────────────────────────
#  STT ENGINE
# ─────────────────────────────────────────────────────────────────────────────

class IgrisSTTEngine:
    """
    Speech-to-Text Engine with multiple backends.
    Priority: Whisper (local) → Google Web Speech (free) → Azure
    """

    def __init__(self) -> None:
        self._whisper_model = None
        self._whisper_model_name = os.getenv("WHISPER_MODEL", "base")  # tiny, base, small, medium, large
        self._listening = False
        self._audio_queue: queue.Queue = queue.Queue()
        self._callbacks: List[Callable] = []
        self._wake_words = ["igris", "arise igris", "hey igris", "ایگرس"]

    def _load_whisper(self) -> bool:
        """Lazy-load Whisper model."""
        if not _WHISPER:
            return False
        if self._whisper_model is not None:
            return True
        try:
            logger.info(f"[STT] Loading Whisper model: {self._whisper_model_name}...")
            self._whisper_model = openai_whisper.load_model(self._whisper_model_name)
            logger.info("[STT] ⚡ Whisper model loaded.")
            return True
        except Exception as e:
            logger.error(f"[STT] Whisper load failed: {e}")
            return False

    async def transcribe_file(self, audio_path: str) -> TranscriptionResult:
        """Transcribe an audio file using Whisper (best quality) or fallback."""
        t_start = time.time()

        # Try Whisper first
        if _WHISPER and self._load_whisper():
            try:
                result = await asyncio.to_thread(
                    self._whisper_model.transcribe,
                    audio_path,
                    fp16=False,
                )
                return TranscriptionResult(
                    text=result["text"].strip(),
                    language=result.get("language", "en"),
                    confidence=0.95,
                    duration_ms=(time.time() - t_start) * 1000,
                    engine="whisper",
                )
            except Exception as e:
                logger.warning(f"[STT] Whisper error: {e}")

        # Fallback: Google Web Speech (free, needs internet)
        if _SR:
            try:
                recognizer = sr.Recognizer()
                with sr.AudioFile(audio_path) as source:
                    audio = recognizer.record(source)
                text = recognizer.recognize_google(audio, language="ur-PK")  # Urdu support
                return TranscriptionResult(
                    text=text,
                    language="ur",
                    confidence=0.80,
                    duration_ms=(time.time() - t_start) * 1000,
                    engine="google",
                )
            except Exception as e:
                logger.warning(f"[STT] Google STT error: {e}")

        return TranscriptionResult(
            text="", language="", confidence=0.0,
            duration_ms=(time.time() - t_start) * 1000,
            engine="none", success=False,
            error="No STT engine available"
        )

    async def transcribe_bytes(self, audio_bytes: bytes, format: str = "wav") -> TranscriptionResult:
        """Transcribe audio bytes (from microphone/upload)."""
        with tempfile.NamedTemporaryFile(suffix=f".{format}", delete=False) as tmp:
            tmp.write(audio_bytes)
            tmp_path = tmp.name
        try:
            return await self.transcribe_file(tmp_path)
        finally:
            try:
                os.unlink(tmp_path)
            except Exception:
                pass

    async def record_and_transcribe(self, duration_seconds: float = 5.0) -> TranscriptionResult:
        """Record from microphone and transcribe."""
        t_start = time.time()

        if _SOUNDDEVICE:
            try:
                sample_rate = 16000
                logger.info(f"[STT] Recording {duration_seconds}s from microphone...")
                audio_data = await asyncio.to_thread(
                    sd.rec,
                    int(duration_seconds * sample_rate),
                    samplerate=sample_rate,
                    channels=1,
                    dtype="float32",
                )
                await asyncio.to_thread(sd.wait)

                # Save to temp WAV
                import scipy.io.wavfile as wavfile
                with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
                    wavfile.write(tmp.name, sample_rate, audio_data)
                    tmp_path = tmp.name

                result = await self.transcribe_file(tmp_path)
                os.unlink(tmp_path)
                return result

            except Exception as e:
                logger.warning(f"[STT] sounddevice recording failed: {e}")

        if _SR:
            try:
                recognizer = sr.Recognizer()
                mic = sr.Microphone()
                with mic as source:
                    recognizer.adjust_for_ambient_noise(source, duration=0.5)
                    audio = recognizer.listen(source, timeout=duration_seconds, phrase_time_limit=duration_seconds)
                text = recognizer.recognize_google(audio)
                return TranscriptionResult(
                    text=text, language="en", confidence=0.80,
                    duration_ms=(time.time() - t_start) * 1000,
                    engine="google_live",
                )
            except Exception as e:
                pass

        return TranscriptionResult(
            text="", language="", confidence=0.0,
            duration_ms=(time.time() - t_start) * 1000,
            engine="none", success=False,
            error="No microphone/STT available. Install sounddevice or SpeechRecognition."
        )

    def check_wake_word(self, text: str) -> bool:
        """Check if text contains a wake word."""
        text_lower = text.lower().strip()
        return any(ww in text_lower for ww in self._wake_words)

    def get_status(self) -> Dict[str, Any]:
        return {
            "whisper_available": _WHISPER,
            "whisper_model": self._whisper_model_name,
            "whisper_loaded": self._whisper_model is not None,
            "google_stt_available": _SR,
            "sounddevice_available": _SOUNDDEVICE,
            "pyaudio_available": _PYAUDIO,
        }


# ─────────────────────────────────────────────────────────────────────────────
#  TTS ENGINE
# ─────────────────────────────────────────────────────────────────────────────

class IgrisTTSEngine:
    """
    Text-to-Speech Engine with multiple backends.
    Priority: ElevenLabs (premium) → OpenAI TTS → pyttsx3 (local)
    """

    ELEVENLABS_VOICES = {
        "igris":   "EXAVITQu4vr4xnSDxMaL",   # Dramatic/Deep voice
        "default": "21m00Tcm4TlvDq8ikWAM",   # Rachel — warm voice
        "male":    "VR6AewLTigWG4xSOukaG",   # Arnold — strong
    }

    def __init__(self) -> None:
        self._el_api_key = os.getenv("ELEVENLABS_API_KEY", "")
        self._openai_key = os.getenv("OPENAI_API_KEY", "")
        self._preferred_engine = self._detect_best_engine()
        self._voice_id = self.ELEVENLABS_VOICES["igris"]

    def _detect_best_engine(self) -> str:
        if os.getenv("ELEVENLABS_API_KEY"):
            return "elevenlabs"
        if os.getenv("OPENAI_API_KEY"):
            return "openai_tts"
        if _PYTTSX3:
            return "pyttsx3"
        return "none"

    async def speak(self, text: str, return_audio: bool = False) -> TTSResult:
        """Convert text to speech. Returns audio as base64 if return_audio=True."""
        t_start = time.time()
        text = text.strip()
        if not text:
            return TTSResult(text="", engine="none", audio_b64=None, duration_ms=0, success=False, error="Empty text")

        # ── ElevenLabs ────────────────────────────────────────────────────────
        if self._el_api_key:
            result = await self._elevenlabs_tts(text)
            if result.success:
                result.duration_ms = (time.time() - t_start) * 1000
                # Also play locally
                if not return_audio:
                    await self._play_audio_bytes_async(result.audio_b64)
                return result

        # ── OpenAI TTS ────────────────────────────────────────────────────────
        if self._openai_key:
            result = await self._openai_tts(text)
            if result.success:
                result.duration_ms = (time.time() - t_start) * 1000
                if not return_audio:
                    await self._play_audio_bytes_async(result.audio_b64)
                return result

        # ── pyttsx3 (local, no internet) ─────────────────────────────────────
        if _PYTTSX3:
            return self._pyttsx3_speak(text, t_start)

        return TTSResult(
            text=text, engine="none", audio_b64=None,
            duration_ms=(time.time() - t_start) * 1000,
            success=False, error="No TTS engine available"
        )

    async def _elevenlabs_tts(self, text: str) -> TTSResult:
        try:
            url = f"https://api.elevenlabs.io/v1/text-to-speech/{self._voice_id}"
            headers = {
                "xi-api-key": self._el_api_key,
                "Content-Type": "application/json",
            }
            payload = {
                "text": text,
                "model_id": "eleven_multilingual_v2",
                "voice_settings": {"stability": 0.5, "similarity_boost": 0.75},
            }
            response = await asyncio.to_thread(
                requests.post, url, headers=headers, json=payload, timeout=15
            )
            if response.status_code == 200:
                audio_b64 = base64.b64encode(response.content).decode("utf-8")
                return TTSResult(text=text, engine="elevenlabs", audio_b64=audio_b64, duration_ms=0)
            else:
                return TTSResult(text=text, engine="elevenlabs", audio_b64=None, duration_ms=0,
                                 success=False, error=f"ElevenLabs HTTP {response.status_code}")
        except Exception as e:
            return TTSResult(text=text, engine="elevenlabs", audio_b64=None, duration_ms=0,
                             success=False, error=str(e))

    async def _openai_tts(self, text: str) -> TTSResult:
        try:
            url = "https://api.openai.com/v1/audio/speech"
            headers = {
                "Authorization": f"Bearer {self._openai_key}",
                "Content-Type": "application/json",
            }
            payload = {"model": "tts-1", "input": text[:4096], "voice": "onyx"}
            response = await asyncio.to_thread(
                requests.post, url, headers=headers, json=payload, timeout=15
            )
            if response.status_code == 200:
                audio_b64 = base64.b64encode(response.content).decode("utf-8")
                return TTSResult(text=text, engine="openai_tts", audio_b64=audio_b64, duration_ms=0)
            else:
                return TTSResult(text=text, engine="openai_tts", audio_b64=None, duration_ms=0,
                                 success=False, error=f"OpenAI TTS HTTP {response.status_code}")
        except Exception as e:
            return TTSResult(text=text, engine="openai_tts", audio_b64=None, duration_ms=0,
                             success=False, error=str(e))

    def _pyttsx3_speak(self, text: str, t_start: float) -> TTSResult:
        """Use pyttsx3 for local TTS — runs in thread to avoid COM issues."""
        def run_tts():
            try:
                import pythoncom
                pythoncom.CoInitialize()
            except Exception:
                pass
            try:
                engine = pyttsx3.init()
                engine.setProperty("rate", 145)
                engine.setProperty("volume", 0.9)
                engine.say(text)
                engine.runAndWait()
            except Exception as e:
                logger.error(f"[TTS] pyttsx3 error: {e}")
            finally:
                try:
                    import pythoncom
                    pythoncom.CoUninitialize()
                except Exception:
                    pass

        thread = threading.Thread(target=run_tts, daemon=True)
        thread.start()
        return TTSResult(
            text=text, engine="pyttsx3", audio_b64=None,
            duration_ms=(time.time() - t_start) * 1000,
        )

    async def _play_audio_bytes_async(self, audio_b64: Optional[str]) -> None:
        """Play base64 audio bytes locally."""
        if not audio_b64:
            return
        try:
            audio_bytes = base64.b64decode(audio_b64)
            if _SOUNDDEVICE:
                import soundfile as sf
                buf = io.BytesIO(audio_bytes)
                data, samplerate = await asyncio.to_thread(sf.read, buf)
                await asyncio.to_thread(sd.play, data, samplerate)
                await asyncio.to_thread(sd.wait)
        except Exception as e:
            logger.warning(f"[TTS] Audio playback error: {e}")

    def set_voice(self, voice_name: str) -> None:
        """Switch ElevenLabs voice."""
        if voice_name in self.ELEVENLABS_VOICES:
            self._voice_id = self.ELEVENLABS_VOICES[voice_name]

    def get_status(self) -> Dict[str, Any]:
        return {
            "preferred_engine": self._preferred_engine,
            "elevenlabs_available": bool(self._el_api_key),
            "openai_tts_available": bool(self._openai_key),
            "pyttsx3_available": _PYTTSX3,
            "sounddevice_available": _SOUNDDEVICE,
            "current_voice_id": self._voice_id,
        }


# ─────────────────────────────────────────────────────────────────────────────
#  MASTER VOICE ENGINE
# ─────────────────────────────────────────────────────────────────────────────

class IgrisVoiceEngine:
    """
    Combined STT + TTS engine — the voice of Igris.
    """

    def __init__(self) -> None:
        self.stt = IgrisSTTEngine()
        self.tts = IgrisTTSEngine()
        logger.info("[VOICE] ⚡ Advanced Voice Engine initialized.")

    async def listen_and_respond(
        self,
        duration: float = 5.0,
        on_transcription: Optional[Callable] = None,
    ) -> TranscriptionResult:
        """Record, transcribe, optionally callback."""
        result = await self.stt.record_and_transcribe(duration)
        if result.success and on_transcription:
            await on_transcription(result)
        return result

    async def speak(self, text: str, return_audio: bool = False) -> TTSResult:
        """Speak text via best available engine."""
        return await self.tts.speak(text, return_audio=return_audio)

    async def transcribe_upload(self, audio_bytes: bytes, fmt: str = "wav") -> TranscriptionResult:
        """Transcribe uploaded audio file."""
        return await self.stt.transcribe_bytes(audio_bytes, fmt)

    def get_full_status(self) -> Dict[str, Any]:
        return {
            "stt": self.stt.get_status(),
            "tts": self.tts.get_status(),
        }


# ─────────────────────────────────────────────────────────────────────────────
#  SINGLETON
# ─────────────────────────────────────────────────────────────────────────────

_instance: Optional[IgrisVoiceEngine] = None


def get_voice_engine() -> IgrisVoiceEngine:
    global _instance
    if _instance is None:
        _instance = IgrisVoiceEngine()
    return _instance
