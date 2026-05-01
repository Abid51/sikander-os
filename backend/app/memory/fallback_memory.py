"""
Fallback neural memory when the primary singleton fails to initialize.
Reuses IgrisNeuralMemory with a dedicated persist file (no duplicate logic).
"""

from __future__ import annotations

import os

from app.memory.vector_memory import IgrisNeuralMemory

_FALLBACK_FILE = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "..", "igris_neural_memory_fallback.json")
)


class FallbackMemory(IgrisNeuralMemory):
    """Same capabilities as vector DB; isolated storage path for recovery mode."""

    def __init__(self) -> None:
        super().__init__(persist_path=_FALLBACK_FILE)
