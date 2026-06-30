from __future__ import annotations

from sqlalchemy import JSON, Boolean, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from ..base import TimestampedBase

_PROFILE_FK = "user_profile.id"


class UserProfile(TimestampedBase):
    __tablename__ = "user_profile"

    full_name: Mapped[str | None] = mapped_column(String, nullable=True)
    headline: Mapped[str | None] = mapped_column(String, nullable=True)
    email: Mapped[str | None] = mapped_column(String, nullable=True)
    phone: Mapped[str | None] = mapped_column(String, nullable=True)
    location: Mapped[str | None] = mapped_column(String, nullable=True)
    work_auth: Mapped[str | None] = mapped_column(String, nullable=True)
    default_language: Mapped[str] = mapped_column(String, default="en")
    links: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)


class WorkExperience(TimestampedBase):
    __tablename__ = "work_experience"

    profile_id: Mapped[int] = mapped_column(ForeignKey(_PROFILE_FK, ondelete="CASCADE"))
    company: Mapped[str | None] = mapped_column(String, nullable=True)
    title: Mapped[str | None] = mapped_column(String, nullable=True)
    employment_type: Mapped[str | None] = mapped_column(String, nullable=True)
    location: Mapped[str | None] = mapped_column(String, nullable=True)
    remote: Mapped[str | None] = mapped_column(String, nullable=True)
    start_date: Mapped[str | None] = mapped_column(String, nullable=True)
    end_date: Mapped[str | None] = mapped_column(String, nullable=True)
    is_current: Mapped[bool] = mapped_column(Boolean, default=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    achievements: Mapped[list | None] = mapped_column(JSON, nullable=True)
    tech_stack: Mapped[list | None] = mapped_column(JSON, nullable=True)
    order_index: Mapped[int] = mapped_column(Integer, default=0)


class Education(TimestampedBase):
    __tablename__ = "education"

    profile_id: Mapped[int] = mapped_column(ForeignKey(_PROFILE_FK, ondelete="CASCADE"))
    institution: Mapped[str | None] = mapped_column(String, nullable=True)
    degree: Mapped[str | None] = mapped_column(String, nullable=True)
    field: Mapped[str | None] = mapped_column(String, nullable=True)
    start_date: Mapped[str | None] = mapped_column(String, nullable=True)
    end_date: Mapped[str | None] = mapped_column(String, nullable=True)
    grade: Mapped[str | None] = mapped_column(String, nullable=True)
    location: Mapped[str | None] = mapped_column(String, nullable=True)
    order_index: Mapped[int] = mapped_column(Integer, default=0)


class Skill(TimestampedBase):
    __tablename__ = "skills"

    profile_id: Mapped[int] = mapped_column(ForeignKey(_PROFILE_FK, ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String)
    category: Mapped[str | None] = mapped_column(String, nullable=True)
    level: Mapped[str | None] = mapped_column(String, nullable=True)
    years: Mapped[float | None] = mapped_column(Float, nullable=True)
    last_used: Mapped[str | None] = mapped_column(String, nullable=True)


class Language(TimestampedBase):
    __tablename__ = "languages"

    profile_id: Mapped[int] = mapped_column(ForeignKey(_PROFILE_FK, ondelete="CASCADE"))
    language: Mapped[str] = mapped_column(String)
    cefr_level: Mapped[str | None] = mapped_column(String, nullable=True)
    certified: Mapped[bool] = mapped_column(Boolean, default=False)


class Certification(TimestampedBase):
    __tablename__ = "certifications"

    profile_id: Mapped[int] = mapped_column(ForeignKey(_PROFILE_FK, ondelete="CASCADE"))
    name: Mapped[str | None] = mapped_column(String, nullable=True)
    issuer: Mapped[str | None] = mapped_column(String, nullable=True)
    issued: Mapped[str | None] = mapped_column(String, nullable=True)
    expires: Mapped[str | None] = mapped_column(String, nullable=True)
    credential_id: Mapped[str | None] = mapped_column(String, nullable=True)
    url: Mapped[str | None] = mapped_column(String, nullable=True)


class Project(TimestampedBase):
    __tablename__ = "projects"

    profile_id: Mapped[int] = mapped_column(ForeignKey(_PROFILE_FK, ondelete="CASCADE"))
    name: Mapped[str | None] = mapped_column(String, nullable=True)
    role: Mapped[str | None] = mapped_column(String, nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    tech: Mapped[list | None] = mapped_column(JSON, nullable=True)
    url: Mapped[str | None] = mapped_column(String, nullable=True)
    start_date: Mapped[str | None] = mapped_column(String, nullable=True)
    end_date: Mapped[str | None] = mapped_column(String, nullable=True)


class Publication(TimestampedBase):
    __tablename__ = "publications"

    profile_id: Mapped[int] = mapped_column(ForeignKey(_PROFILE_FK, ondelete="CASCADE"))
    title: Mapped[str | None] = mapped_column(String, nullable=True)
    venue: Mapped[str | None] = mapped_column(String, nullable=True)
    year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    url: Mapped[str | None] = mapped_column(String, nullable=True)
    authors: Mapped[list | None] = mapped_column(JSON, nullable=True)
