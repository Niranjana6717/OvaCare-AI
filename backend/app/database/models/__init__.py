"""
Importing this module registers every ORM model on `Base.metadata`, which is
what `Base.metadata.create_all()` (dev/test bootstrap) and Alembic's
autogenerate need to see the full schema.
"""
from app.database.models.audit_log import AuditLog
from app.database.models.assessment import Assessment, Prediction, ScreeningOutcome
from app.database.models.consent import ConsentRecord, ConsentType
from app.database.models.cycle import CycleRecord, FlowLevel
from app.database.models.model_version import ModelStage, ModelVersion
from app.database.models.notification import Notification, NotificationPreference, NotificationType
from app.database.models.symptom import Symptom, SymptomType
from app.database.models.token import RevokedToken
from app.database.models.user import Profile, User, UserRole

__all__ = [
    "RevokedToken",
    "AuditLog",
    "Assessment",
    "Prediction",
    "ScreeningOutcome",
    "ConsentRecord",
    "ConsentType",
    "CycleRecord",
    "FlowLevel",
    "ModelStage",
    "ModelVersion",
    "Notification",
    "NotificationPreference",
    "NotificationType",
    "Symptom",
    "SymptomType",
    "Profile",
    "User",
    "UserRole",
]
