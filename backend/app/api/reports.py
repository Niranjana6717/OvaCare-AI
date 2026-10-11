from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.database.database import get_db
from app.database.models.user import User
from app.security.dependencies import get_current_user
from app.services.report_pdf_service import build_health_report_pdf
from app.services.report_service import ALL_SECTIONS, generate_health_report

router = APIRouter(prefix="/reports", tags=["reports"])


@router.get("")
def get_report(
    sections: list[str] = Query(default=list(ALL_SECTIONS)),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return generate_health_report(db, user.id, sections)


@router.get("/pdf")
def get_report_pdf(
    sections: list[str] = Query(default=list(ALL_SECTIONS)),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Same report data as GET /reports (JSON, unchanged), rendered as a
    downloadable PDF. Additive — does not replace the JSON export."""
    report = generate_health_report(db, user.id, sections)
    pdf_bytes = build_health_report_pdf(report)
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": 'attachment; filename="ovacare-health-report.pdf"'},
    )
