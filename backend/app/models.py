"""SQLAlchemy 数据模型。"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from app.database import Base


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="draft", server_default="draft"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now(), onupdate=func.now()
    )

    project_templates: Mapped[list["ProjectTemplate"]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )
    variables: Mapped[list["Variable"]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )
    generation_tasks: Mapped[list["GenerationTask"]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )
    generated_files: Mapped[list["GeneratedFile"]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )
    ai_logs: Mapped[list["AILog"]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )


class Template(Base):
    __tablename__ = "templates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    category: Mapped[str] = mapped_column(String(64), nullable=False, default="other")
    tags: Mapped[list | None] = mapped_column(JSON, nullable=True, default=list)
    applicable_scenarios: Mapped[str | None] = mapped_column(Text, nullable=True)
    variable_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_preset: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    file_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    variables_json: Mapped[list | None] = mapped_column(JSON, nullable=True, default=list)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    preview_image: Mapped[str | None] = mapped_column(String(512), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now(), onupdate=func.now()
    )

    project_templates: Mapped[list["ProjectTemplate"]] = relationship(
        back_populates="template"
    )
    generated_files: Mapped[list["GeneratedFile"]] = relationship(back_populates="template")


class ProjectTemplate(Base):
    __tablename__ = "project_templates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    template_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("templates.id", ondelete="CASCADE"), nullable=False
    )
    template_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    variables_snapshot_json: Mapped[list | None] = mapped_column(
        JSON, nullable=True, default=list
    )

    project: Mapped["Project"] = relationship(back_populates="project_templates")
    template: Mapped["Template"] = relationship(back_populates="project_templates")


class Variable(Base):
    __tablename__ = "variables"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    key: Mapped[str] = mapped_column(String(128), nullable=False)
    label: Mapped[str] = mapped_column(String(255), nullable=False)
    value: Mapped[str | None] = mapped_column(Text, nullable=True)
    data_type: Mapped[str] = mapped_column(String(32), nullable=False, default="text")
    category: Mapped[str] = mapped_column(String(64), nullable=False, default="other")
    is_multiple: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    source_template_ids: Mapped[list | None] = mapped_column(
        JSON, nullable=True, default=list
    )
    is_merged: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    merged_from_keys: Mapped[list | None] = mapped_column(JSON, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now(), onupdate=func.now()
    )

    project: Mapped["Project"] = relationship(back_populates="variables")


class CustomVariable(Base):
    __tablename__ = "custom_variables"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    key: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)
    label: Mapped[str] = mapped_column(String(255), nullable=False)
    category: Mapped[str] = mapped_column(String(64), nullable=False, default="other")
    data_type: Mapped[str] = mapped_column(String(32), nullable=False, default="text")
    aliases: Mapped[list | None] = mapped_column(JSON, nullable=True, default=list)
    created_by_template_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("templates.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )


class GenerationTask(Base):
    __tablename__ = "generation_tasks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="pending", server_default="pending"
    )
    total_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    completed_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now(), onupdate=func.now()
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    project: Mapped["Project"] = relationship(back_populates="generation_tasks")


class GeneratedFile(Base):
    __tablename__ = "generated_files"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    template_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("templates.id", ondelete="CASCADE"), nullable=False
    )
    file_path: Mapped[str] = mapped_column(String(512), nullable=False)
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="completed", server_default="completed"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )

    project: Mapped["Project"] = relationship(back_populates="generated_files")
    template: Mapped["Template"] = relationship(back_populates="generated_files")


class AILog(Base):
    __tablename__ = "ai_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("projects.id", ondelete="SET NULL"), nullable=True
    )
    ai_type: Mapped[str] = mapped_column(String(64), nullable=False)
    prompt: Mapped[str | None] = mapped_column(Text, nullable=True)
    response: Mapped[str | None] = mapped_column(Text, nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    validation_result: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    user_action: Mapped[str | None] = mapped_column(String(32), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )

    project: Mapped["Project | None"] = relationship(back_populates="ai_logs")
