"""
PDF health report export.

Requirement: "Keep the existing JSON report functionality. ADD PDF export
without removing JSON export." This module does exactly that — it never
re-queries the database itself. `build_health_report_pdf()` takes the SAME
`report` dict that `app.services.report_service.generate_health_report()`
already builds for the JSON endpoint, so there is exactly one code path
that decides what a report contains (which sections the user selected,
what a screening result says); this module only decides how to lay it out
as a PDF. No SQLAlchemy import here — like app/safety/wording.py and
app/services/cycle_math.py, this module is pure and directly unit-testable
without a database (see backend/tests/test_report_pdf_service.py).
"""
from __future__ import annotations

import io
import statistics
from datetime import date, datetime, timezone
from typing import Any

from reportlab.lib import colors
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    HRFlowable,
    ListFlowable,
    ListItem,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from app.safety.wording import MEDICAL_DISCLAIMER, PDF_REPORT_DISCLAIMER, assert_safe_wording
from app.services import cycle_math

_STYLES = getSampleStyleSheet()
_H1 = ParagraphStyle("OvaCareH1", parent=_STYLES["Heading1"], textColor=colors.HexColor("#5f2f7d"))
_H2 = ParagraphStyle("OvaCareH2", parent=_STYLES["Heading2"], textColor=colors.HexColor("#5f2f7d"), spaceBefore=14)
_H3 = ParagraphStyle("OvaCareH3", parent=_STYLES["Heading3"], spaceBefore=6)
_BODY = _STYLES["BodyText"]
_MUTED = ParagraphStyle("OvaCareMuted", parent=_BODY, textColor=colors.HexColor("#6b6472"), fontSize=9)
_DISCLAIMER = ParagraphStyle(
    "OvaCareDisclaimer",
    parent=_BODY,
    borderColor=colors.HexColor("#c23b3b"),
    borderWidth=1,
    borderPadding=8,
    backColor=colors.HexColor("#fbeaea"),
)


def _cycle_summary_from_history(cycle_history: list[dict]) -> cycle_math.CycleSummary:
    # report_service.py orders cycle_history start_date DESC;
    # cycle_math.summarize() expects ascending order (it diffs each entry
    # against the PREVIOUS start_date), same contract cycle_service.py uses.
    ordered = sorted(cycle_history, key=lambda c: c["start_date"])
    entries = [
        cycle_math.CycleEntry(
            start_date=date.fromisoformat(c["start_date"]),
            end_date=date.fromisoformat(c["end_date"]) if c.get("end_date") else None,
        )
        for c in ordered
    ]
    return cycle_math.summarize(entries, insufficient_data_message="Not enough cycle history for a summary.")


def _symptom_summary(symptom_history: list[dict]) -> dict[str, Any]:
    if not symptom_history:
        return {"total_logged": 0, "by_type": {}}
    by_type: dict[str, list[int]] = {}
    for s in symptom_history:
        by_type.setdefault(s["symptom_type"], []).append(s["severity"])
    return {
        "total_logged": len(symptom_history),
        "by_type": {
            symptom_type: {"count": len(severities), "average_severity": round(statistics.mean(severities), 1)}
            for symptom_type, severities in by_type.items()
        },
    }


def _table(rows: list[list[str]], header: bool = False) -> Table:
    t = Table(rows, hAlign="LEFT")
    style = [
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("LINEBELOW", (0, 0), (-1, -1), 0.5, colors.HexColor("#e6e1ea")),
    ]
    if header:
        style.append(("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"))
        style.append(("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#5f2f7d")))
    t.setStyle(TableStyle(style))
    return t


def build_health_report_pdf(report: dict[str, Any]) -> bytes:
    """Render `report` (exactly the dict `generate_health_report()` returns)
    as a PDF. A section absent from `report` — because the user didn't
    select it (requirement #35/#85) — is simply absent from the PDF too;
    this function never adds a section on its own."""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=LETTER,
        leftMargin=0.75 * inch,
        rightMargin=0.75 * inch,
        topMargin=0.75 * inch,
        bottomMargin=0.75 * inch,
        title="OvaCare AI Health Report",
    )
    story: list[Any] = []

    story.append(Paragraph("OvaCare AI — Health Report", _H1))
    generated_at = report.get("generated_at", datetime.now(timezone.utc).isoformat())
    story.append(Paragraph(f"Generated {generated_at}", _MUTED))
    story.append(Spacer(1, 12))

    assert_safe_wording(PDF_REPORT_DISCLAIMER)
    story.append(Paragraph(PDF_REPORT_DISCLAIMER, _DISCLAIMER))
    story.append(Spacer(1, 16))

    if report.get("profile") is not None:
        p = report["profile"]
        story.append(Paragraph("Profile", _H2))
        rows = [
            ["Name", p.get("full_name") or "—"],
            ["Date of birth", p.get("date_of_birth") or "—"],
            ["Height (cm)", str(p["height_cm"]) if p.get("height_cm") is not None else "—"],
            ["Weight (kg)", str(p["weight_kg"]) if p.get("weight_kg") is not None else "—"],
            ["BMI", str(p["bmi"]) if p.get("bmi") is not None else "—"],
            ["Country", p.get("country") or "—"],
        ]
        story.append(_table(rows))
        story.append(Spacer(1, 10))

    if "cycle_history" in report:
        story.append(Paragraph("Cycle Summary", _H2))
        summary = _cycle_summary_from_history(report["cycle_history"])
        if summary.sufficient_data:
            rows = [
                ["Average cycle length", f"{summary.average_cycle_length_days} days"],
                [
                    "Average period duration",
                    f"{summary.average_period_duration_days} days" if summary.average_period_duration_days else "—",
                ],
                ["Cycle variability", f"±{summary.cycle_variability_stdev_days} days"],
                ["Cycles logged", str(len(report["cycle_history"]))],
            ]
            story.append(_table(rows))
            if summary.is_high_variability:
                story.append(Spacer(1, 4))
                story.append(
                    Paragraph(
                        "Your recent cycle lengths have varied. Continue tracking your cycles, and consider "
                        "discussing persistent changes with a qualified healthcare professional.",
                        _MUTED,
                    )
                )
        else:
            story.append(Paragraph(summary.message or "Not enough cycle history for a summary.", _MUTED))
        story.append(Spacer(1, 10))

    if "symptom_history" in report:
        story.append(Paragraph("Symptom Summary", _H2))
        summary = _symptom_summary(report["symptom_history"])
        if summary["total_logged"]:
            rows = [["Symptom", "Times logged", "Average severity"]]
            for symptom_type, stats in summary["by_type"].items():
                rows.append(
                    [symptom_type.replace("_", " ").title(), str(stats["count"]), str(stats["average_severity"])]
                )
            story.append(_table(rows, header=True))
        else:
            story.append(Paragraph("No symptoms logged.", _MUTED))
        story.append(Spacer(1, 10))

    if "screening_history" in report:
        story.append(Paragraph("AI Screening Result", _H2))
        history = report["screening_history"]
        if not history:
            story.append(Paragraph("No screening assessments completed yet.", _MUTED))
        else:
            # report_service.py orders this list by the owning assessment's
            # submitted_at DESC, so index 0 is the most recent.
            latest = history[0]
            assert_safe_wording(latest["message"])
            story.append(Paragraph(f"Most recent — assessed {latest.get('assessed_at', '—')}", _H3))
            story.append(Paragraph(latest["message"], _BODY))
            if latest.get("probability") is not None:
                story.append(Paragraph(f"Model probability: {latest['probability'] * 100:.0f}%", _MUTED))

            factors = (latest.get("explanation") or {}).get("factors") or []
            if factors:
                story.append(Spacer(1, 6))
                story.append(Paragraph("Important contributing factors:", _BODY))
                story.append(
                    ListFlowable(
                        [
                            ListItem(Paragraph(f"{f['label']} — {f['why_it_matters']}", _BODY))
                            for f in factors
                        ],
                        bulletType="bullet",
                    )
                )
            story.append(Spacer(1, 6))
            story.append(Paragraph(f"Model version: {latest.get('model_version', 'unavailable')}", _MUTED))
            if len(history) > 1:
                story.append(
                    Paragraph(
                        f"{len(history) - 1} earlier screening result(s) also on file "
                        "(see in-app history for full detail).",
                        _MUTED,
                    )
                )
        story.append(Spacer(1, 10))

    story.append(Spacer(1, 12))
    story.append(HRFlowable(width="100%", color=colors.HexColor("#e6e1ea")))
    story.append(Spacer(1, 6))
    story.append(Paragraph(MEDICAL_DISCLAIMER.replace("\n\n", " "), _MUTED))

    doc.build(story)
    return buffer.getvalue()
