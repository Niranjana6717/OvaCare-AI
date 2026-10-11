"""OvaCare AI — FastAPI application entrypoint."""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from app.api import admin, assessments, auth, consent, cycles, insights, notifications, predictions, reports, symptoms, users
from app.config import get_settings
from app.logging_config import configure_logging
from app.middleware.error_handling import register_exception_handlers
from app.middleware.rate_limit import limiter

settings = get_settings()
configure_logging(settings.ENVIRONMENT)

app = FastAPI(
    title="OvaCare AI API",
    description=(
        "OvaCare AI backend: menstrual cycle tracking, symptom tracking, and "
        "AI-assisted PCOS screening. Screening results are informational and "
        "do not diagnose PCOS or any other medical condition."
    ),
    version="0.1.0",
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, lambda request, exc: _rate_limit_handler(request, exc))
app.add_middleware(SlowAPIMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

register_exception_handlers(app)


def _rate_limit_handler(request, exc):
    from fastapi.responses import JSONResponse

    return JSONResponse(status_code=429, content={"detail": "Too many requests. Please try again shortly."})


API_PREFIX = settings.API_V1_PREFIX

app.include_router(auth.router, prefix=API_PREFIX)
app.include_router(users.router, prefix=API_PREFIX)
app.include_router(assessments.router, prefix=API_PREFIX)
app.include_router(predictions.router, prefix=API_PREFIX)
app.include_router(cycles.router, prefix=API_PREFIX)
app.include_router(symptoms.router, prefix=API_PREFIX)
app.include_router(insights.router, prefix=API_PREFIX)
app.include_router(reports.router, prefix=API_PREFIX)
app.include_router(notifications.router, prefix=API_PREFIX)
app.include_router(consent.router, prefix=API_PREFIX)
app.include_router(admin.router, prefix=API_PREFIX)


@app.get("/health")
def health_check():
    """Unauthenticated liveness probe — no user or health data, just process status."""
    return {"status": "ok"}
