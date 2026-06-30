"""Importa tutti i modelli così che ``Base.metadata`` sia completo (Alembic, create_all)."""

from .answers import ApprovedAnswer, CoverLetterTemplate
from .applications import Application
from .browser import ActionLog, Intervention, PageSnapshot
from .companies import Company
from .jobs import JobMatch, JobPosting
from .portals import Portal
from .preferences import Preferences
from .profile import (
    Certification,
    Education,
    Language,
    Project,
    Publication,
    Skill,
    UserProfile,
    WorkExperience,
)
from .provenance import FieldProvenance
from .search import SearchRun

__all__ = [
    "UserProfile",
    "WorkExperience",
    "Education",
    "Skill",
    "Language",
    "Certification",
    "Project",
    "Publication",
    "Preferences",
    "Portal",
    "Company",
    "SearchRun",
    "JobPosting",
    "JobMatch",
    "Application",
    "ApprovedAnswer",
    "CoverLetterTemplate",
    "PageSnapshot",
    "ActionLog",
    "Intervention",
    "FieldProvenance",
]
