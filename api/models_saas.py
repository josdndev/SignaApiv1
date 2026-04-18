from __future__ import annotations

from datetime import date, datetime, timezone
from enum import Enum
from typing import List, Optional
from uuid import uuid4

from sqlmodel import Field, Relationship, SQLModel
from sqlalchemy import Column, DateTime, Enum as SAEnum, Index, UniqueConstraint, func


def _uuid_str() -> str:
    return str(uuid4())


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class TenantRole(str, Enum):
    OWNER = "owner"
    ADMIN = "admin"
    DOCTOR = "doctor"
    NURSE = "nurse"
    RECEPTIONIST = "receptionist"
    ANALYST = "analyst"


ROLE_HIERARCHY = {
    TenantRole.OWNER: 60,
    TenantRole.ADMIN: 50,
    TenantRole.DOCTOR: 40,
    TenantRole.NURSE: 30,
    TenantRole.RECEPTIONIST: 20,
    TenantRole.ANALYST: 10,
}


class PatientStatus(str, Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    ARCHIVED = "archived"
    TRANSFERRED = "transferred"
    DECEASED = "deceased"


class ClinicalRecordStatus(str, Enum):
    OPEN = "open"
    CLOSED = "closed"
    ARCHIVED = "archived"


class VisitStatus(str, Enum):
    SCHEDULED = "scheduled"
    CHECKED_IN = "checked_in"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    NO_SHOW = "no_show"


class DiagnosisStatus(str, Enum):
    PROVISIONAL = "provisional"
    CONFIRMED = "confirmed"
    DIFFERENTIAL = "differential"
    RULED_OUT = "ruled_out"


class AuditAction(str, Enum):
    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"
    LOGIN = "login"
    LOGOUT = "logout"
    ASSIGN_ROLE = "assign_role"
    EXPORT = "export"
    IMPORT = "import"
    ACCESS = "access"


class TimestampMixin(SQLModel):
    id: str = Field(default_factory=_uuid_str, primary_key=True)
    created_at: datetime = Field(
        default_factory=_utcnow,
        sa_type=DateTime(timezone=True),
        sa_column_kwargs={
            "nullable": False,
            "server_default": func.now(),
        },
    )
    updated_at: datetime = Field(
        default_factory=_utcnow,
        sa_type=DateTime(timezone=True),
        sa_column_kwargs={
            "nullable": False,
            "server_default": func.now(),
            "onupdate": func.now(),
        },
    )


class SoftDeleteMixin(SQLModel):
    active: bool = Field(default=True, index=True)
    is_deleted: bool = Field(default=False, index=True)


class Tenant(TimestampMixin, SoftDeleteMixin, table=True):
    __tablename__ = "tenants"
    __table_args__ = (
        UniqueConstraint("slug", name="uq_tenants_slug"),
        Index("ix_tenants_active_created_at", "active", "created_at"),
    )

    name: str = Field(index=True)
    slug: str = Field(index=True)
    timezone: str = Field(default="UTC")
    plan: Optional[str] = Field(default=None)

    memberships: List["Membership"] = Relationship(back_populates="tenant")
    patient_types: List["PatientType"] = Relationship(back_populates="tenant")
    patients: List["Patient"] = Relationship(back_populates="tenant")
    clinical_records: List["ClinicalRecord"] = Relationship(back_populates="tenant")
    visits: List["Visit"] = Relationship(back_populates="tenant")
    diagnoses: List["Diagnosis"] = Relationship(back_populates="tenant")
    audit_logs: List["AuditLog"] = Relationship(back_populates="tenant")


class User(TimestampMixin, SoftDeleteMixin, table=True):
    __tablename__ = "users"
    __table_args__ = (
        UniqueConstraint("email", name="uq_users_email"),
        Index("ix_users_active_email", "active", "email"),
    )

    email: str = Field(index=True)
    full_name: str = Field(index=True)
    password_hash: str
    phone: Optional[str] = Field(default=None, index=True)
    last_login_at: Optional[datetime] = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True),
    )

    memberships: List["Membership"] = Relationship(back_populates="user")
    audit_logs: List["AuditLog"] = Relationship(back_populates="actor_user")
    created_clinical_records: List["ClinicalRecord"] = Relationship(back_populates="created_by_user")
    created_visits: List["Visit"] = Relationship(back_populates="created_by_user")
    created_diagnoses: List["Diagnosis"] = Relationship(back_populates="created_by_user")


class Membership(TimestampMixin, SoftDeleteMixin, table=True):
    __tablename__ = "memberships"
    __table_args__ = (
        UniqueConstraint("tenant_id", "user_id", name="uq_memberships_tenant_user"),
        Index("ix_memberships_tenant_role", "tenant_id", "role"),
        Index("ix_memberships_user_active", "user_id", "active"),
    )

    tenant_id: str = Field(foreign_key="tenants.id", index=True)
    user_id: str = Field(foreign_key="users.id", index=True)
    role: TenantRole = Field(
        sa_column=Column(SAEnum(TenantRole, name="tenant_role"), nullable=False),
    )
    invited_at: Optional[datetime] = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True),
    )
    joined_at: Optional[datetime] = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True),
    )

    tenant: Optional[Tenant] = Relationship(back_populates="memberships")
    user: Optional[User] = Relationship(back_populates="memberships")


class PatientType(TimestampMixin, SoftDeleteMixin, table=True):
    __tablename__ = "patient_types"
    __table_args__ = (
        UniqueConstraint("tenant_id", "name", name="uq_patient_types_tenant_name"),
        Index("ix_patient_types_tenant_active", "tenant_id", "active"),
    )

    tenant_id: str = Field(foreign_key="tenants.id", index=True)
    name: str = Field(index=True)
    slug: Optional[str] = Field(default=None, index=True)
    description: Optional[str] = Field(default=None)

    tenant: Optional[Tenant] = Relationship(back_populates="patient_types")
    patients: List["Patient"] = Relationship(back_populates="patient_type")


class Patient(TimestampMixin, SoftDeleteMixin, table=True):
    __tablename__ = "patients"
    __table_args__ = (
        UniqueConstraint("tenant_id", "medical_record_number", name="uq_patients_tenant_mrn"),
        UniqueConstraint("tenant_id", "document_number", name="uq_patients_tenant_document"),
        Index("ix_patients_tenant_status", "tenant_id", "status"),
        Index("ix_patients_tenant_type_status", "tenant_id", "patient_type_id", "status"),
        Index("ix_patients_tenant_last_visit", "tenant_id", "last_visit_at"),
    )

    tenant_id: str = Field(foreign_key="tenants.id", index=True)
    patient_type_id: str = Field(foreign_key="patient_types.id", index=True)
    medical_record_number: str = Field(index=True)
    document_number: Optional[str] = Field(default=None, index=True)
    first_name: str = Field(index=True)
    last_name: str = Field(index=True)
    date_of_birth: Optional[date] = Field(default=None)
    sex: Optional[str] = Field(default=None)
    phone: Optional[str] = Field(default=None, index=True)
    email: Optional[str] = Field(default=None, index=True)
    address: Optional[str] = Field(default=None)
    emergency_contact_name: Optional[str] = Field(default=None)
    emergency_contact_phone: Optional[str] = Field(default=None)
    allergies: Optional[str] = Field(default=None)
    chronic_conditions: Optional[str] = Field(default=None)
    clinical_summary: Optional[str] = Field(default=None)
    notes: Optional[str] = Field(default=None)
    status: PatientStatus = Field(
        default=PatientStatus.ACTIVE,
        sa_column=Column(SAEnum(PatientStatus, name="patient_status"), nullable=False),
    )
    last_visit_at: Optional[datetime] = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True),
    )

    tenant: Optional[Tenant] = Relationship(back_populates="patients")
    patient_type: Optional[PatientType] = Relationship(back_populates="patients")
    clinical_records: List["ClinicalRecord"] = Relationship(back_populates="patient")
    visits: List["Visit"] = Relationship(back_populates="patient")
    diagnoses: List["Diagnosis"] = Relationship(back_populates="patient")


class ClinicalRecord(TimestampMixin, SoftDeleteMixin, table=True):
    __tablename__ = "clinical_records"
    __table_args__ = (
        UniqueConstraint("tenant_id", "record_number", name="uq_clinical_records_tenant_record"),
        Index("ix_clinical_records_tenant_patient", "tenant_id", "patient_id"),
        Index("ix_clinical_records_tenant_status_opened", "tenant_id", "status", "opened_at"),
    )

    tenant_id: str = Field(foreign_key="tenants.id", index=True)
    patient_id: str = Field(foreign_key="patients.id", index=True)
    created_by_user_id: Optional[str] = Field(default=None, foreign_key="users.id", index=True)
    record_number: str = Field(index=True)
    status: ClinicalRecordStatus = Field(
        default=ClinicalRecordStatus.OPEN,
        sa_column=Column(SAEnum(ClinicalRecordStatus, name="clinical_record_status"), nullable=False),
    )
    opened_at: datetime = Field(
        default_factory=_utcnow,
        sa_column=Column(DateTime(timezone=True), nullable=False, server_default=func.now()),
    )
    closed_at: Optional[datetime] = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True),
    )
    chief_complaint: Optional[str] = Field(default=None)
    summary: Optional[str] = Field(default=None)
    notes: Optional[str] = Field(default=None)

    tenant: Optional[Tenant] = Relationship(back_populates="clinical_records")
    patient: Optional[Patient] = Relationship(back_populates="clinical_records")
    created_by_user: Optional[User] = Relationship(back_populates="created_clinical_records")
    visits: List["Visit"] = Relationship(back_populates="clinical_record")
    diagnoses: List["Diagnosis"] = Relationship(back_populates="clinical_record")


class Visit(TimestampMixin, SoftDeleteMixin, table=True):
    __tablename__ = "visits"
    __table_args__ = (
        Index("ix_visits_tenant_patient", "tenant_id", "patient_id"),
        Index("ix_visits_tenant_record", "tenant_id", "clinical_record_id"),
        Index("ix_visits_tenant_visited_at", "tenant_id", "visited_at"),
    )

    tenant_id: str = Field(foreign_key="tenants.id", index=True)
    patient_id: str = Field(foreign_key="patients.id", index=True)
    clinical_record_id: str = Field(foreign_key="clinical_records.id", index=True)
    created_by_user_id: Optional[str] = Field(default=None, foreign_key="users.id", index=True)
    visited_at: datetime = Field(
        default_factory=_utcnow,
        sa_column=Column(DateTime(timezone=True), nullable=False, server_default=func.now()),
    )
    status: VisitStatus = Field(
        default=VisitStatus.SCHEDULED,
        sa_column=Column(SAEnum(VisitStatus, name="visit_status"), nullable=False),
    )
    reason: Optional[str] = Field(default=None)
    triage_notes: Optional[str] = Field(default=None)
    clinical_notes: Optional[str] = Field(default=None)
    vitals_summary: Optional[str] = Field(default=None)
    location: Optional[str] = Field(default=None)
    duration_minutes: Optional[int] = Field(default=None)
    follow_up_at: Optional[datetime] = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True),
    )

    tenant: Optional[Tenant] = Relationship(back_populates="visits")
    patient: Optional[Patient] = Relationship(back_populates="visits")
    clinical_record: Optional[ClinicalRecord] = Relationship(back_populates="visits")
    created_by_user: Optional[User] = Relationship(back_populates="created_visits")
    diagnoses: List["Diagnosis"] = Relationship(back_populates="visit")


class Diagnosis(TimestampMixin, SoftDeleteMixin, table=True):
    __tablename__ = "diagnoses"
    __table_args__ = (
        Index("ix_diagnoses_tenant_visit", "tenant_id", "visit_id"),
        Index("ix_diagnoses_tenant_patient", "tenant_id", "patient_id"),
        Index("ix_diagnoses_tenant_status", "tenant_id", "status"),
    )

    tenant_id: str = Field(foreign_key="tenants.id", index=True)
    patient_id: str = Field(foreign_key="patients.id", index=True)
    visit_id: str = Field(foreign_key="visits.id", index=True)
    clinical_record_id: str = Field(foreign_key="clinical_records.id", index=True)
    created_by_user_id: Optional[str] = Field(default=None, foreign_key="users.id", index=True)
    code: Optional[str] = Field(default=None, index=True)
    name: str = Field(index=True)
    description: Optional[str] = Field(default=None)
    status: DiagnosisStatus = Field(
        default=DiagnosisStatus.PROVISIONAL,
        sa_column=Column(SAEnum(DiagnosisStatus, name="diagnosis_status"), nullable=False),
    )
    is_primary: bool = Field(default=False, index=True)
    diagnosed_at: datetime = Field(
        default_factory=_utcnow,
        sa_column=Column(DateTime(timezone=True), nullable=False, server_default=func.now()),
    )
    notes: Optional[str] = Field(default=None)

    tenant: Optional[Tenant] = Relationship(back_populates="diagnoses")
    patient: Optional[Patient] = Relationship(back_populates="diagnoses")
    visit: Optional[Visit] = Relationship(back_populates="diagnoses")
    clinical_record: Optional[ClinicalRecord] = Relationship(back_populates="diagnoses")
    created_by_user: Optional[User] = Relationship(back_populates="created_diagnoses")


class AuditLog(TimestampMixin, table=True):
    __tablename__ = "audit_logs"
    __table_args__ = (
        Index("ix_audit_logs_tenant_created", "tenant_id", "created_at"),
        Index("ix_audit_logs_tenant_entity", "tenant_id", "entity_type", "entity_id"),
        Index("ix_audit_logs_actor_created", "actor_user_id", "created_at"),
    )

    tenant_id: str = Field(foreign_key="tenants.id", index=True)
    actor_user_id: Optional[str] = Field(default=None, foreign_key="users.id", index=True)
    entity_type: str = Field(index=True)
    entity_id: str = Field(index=True)
    action: AuditAction = Field(
        sa_column=Column(SAEnum(AuditAction, name="audit_action"), nullable=False),
    )
    message: Optional[str] = Field(default=None)
    details: Optional[str] = Field(default=None)
    ip_address: Optional[str] = Field(default=None)
    user_agent: Optional[str] = Field(default=None)

    tenant: Optional[Tenant] = Relationship(back_populates="audit_logs")
    actor_user: Optional[User] = Relationship(back_populates="audit_logs")
