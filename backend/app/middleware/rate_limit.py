"""Simple per-client rate limiting via slowapi (in-memory limiter — for
production, back it with Redis; see docs/deployment.md)."""
from __future__ import annotations

from slowapi import Limiter
from slowapi.util import get_remote_address

from app.config import get_settings

settings = get_settings()

limiter = Limiter(key_func=get_remote_address, default_limits=[f"{settings.RATE_LIMIT_PER_MINUTE}/minute"])
