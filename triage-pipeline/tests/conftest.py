"""Shared test fixtures."""

from __future__ import annotations

import os
import sys
from pathlib import Path

# Ensure src/ is importable
ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

# Force test-friendly env BEFORE any app import
os.environ.setdefault("ENV", "test")
os.environ.setdefault("LOG_LEVEL", "WARNING")
os.environ.setdefault("LOG_FORMAT", "console")
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/15")
os.environ.setdefault("LLM_PRIMARY_MODEL", "stub/none")
os.environ.setdefault("LLM_FALLBACK_MODELS", "")

import pytest  # noqa: E402


@pytest.fixture
def sample_inputs() -> list[dict[str, str]]:
    """The five samples from the assessment brief."""
    return [
        {"source": "chat", "body": "Hi, I'm trying to book a math tutor for IGCSE but I can't see any available time slots after selecting the teacher."},
        {"source": "web_form", "body": "It would be really helpful if we could compare tutors based on ratings, price, and availability in one view before booking."},
        {"source": "chat", "body": "I booked a session yesterday but I didn't receive any confirmation email or session details. Can you check if my booking went through?"},
        {"source": "chat", "body": "Is there a way to get help choosing the right major or university based on my interests?"},
        {"source": "web_form", "body": "The platform is not loading properly and none of the tutors are showing up. Multiple users are facing the same issue."},
    ]
