"""Enum applicativi memorizzati come stringa (``.value``) nelle colonne String.

Niente CHECK constraint a livello DB: mantiene le migrazioni SQLite semplici e flessibili.
"""

from __future__ import annotations

from enum import Enum


class Provenance(str, Enum):
    CERTAIN = "certain"
    DECLARED = "declared"
    INFERRED = "inferred"
    MISSING = "missing"


class SubmitMode(str, Enum):
    MANUAL = "manual"
    SEMI = "semi"
    AUTO = "auto"


class ReapplyPolicy(str, Enum):
    BLOCK = "block"
    WARN = "warn"
    ALLOW = "allow"


class RemotePref(str, Enum):
    REMOTE = "remote"
    HYBRID = "hybrid"
    ONSITE = "onsite"
    ANY = "any"


class AutomationPolicy(str, Enum):
    AUTO = "auto"
    SEMI = "semi"
    MANUAL = "manual"
    READ_ONLY = "read_only"


class TosRisk(str, Enum):
    LOW = "low"
    MED = "med"
    HIGH = "high"
    EXTREME = "extreme"


class SearchRunStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"


class MatchStatus(str, Enum):
    NEW = "new"
    SHORTLISTED = "shortlisted"
    REJECTED = "rejected"
    APPLIED = "applied"
    SKIPPED = "skipped"


class ApplicationStatus(str, Enum):
    DRAFT = "draft"
    IN_PROGRESS = "in_progress"
    NEEDS_USER = "needs_user"
    SUBMITTED = "submitted"
    FAILED = "failed"


class InterventionType(str, Enum):
    CAPTCHA = "captcha"
    LOGIN = "login"
    TWO_FA = "2fa"
    AMBIGUOUS = "ambiguous"
    MISSING_DATA = "missing_data"
    TOS_GATE = "tos_gate"


class InterventionStatus(str, Enum):
    PENDING = "pending"
    RESOLVED = "resolved"
    TIMEOUT = "timeout"
    CANCELLED = "cancelled"


class Actor(str, Enum):
    AGENT = "agent"
    USER = "user"
    SYSTEM = "system"


class AppliedState(str, Enum):
    """Esito di check_application_status (piano §6)."""

    NONE = "none"
    PREPARED = "prepared"
    SUBMITTED = "submitted"


class MatchStrength(str, Enum):
    STRONG = "strong"
    FUZZY = "fuzzy"
