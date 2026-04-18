from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from .models_saas import PatientStatus, TenantRole, VisitStatus


class SaasBaseModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class SaasTenantRead(SaasBaseModel):
    id: str
    name: str
    slug: str
    timezone: str
    plan: Optional[str] = None
    active: bool
    created_at: datetime


class SaasUserRead(SaasBaseModel):
    id: str
    email: str
    full_name: str
    phone: Optional[str] = None
    active: bool
    role: TenantRole
    created_at: datetime


class SaasTokenRead(SaasBaseModel):
    access_token: str
    token_type: str = "bearer"
    tenant: SaasTenantRead
    user: SaasUserRead


class SaasBootstrapCreate(SaasBaseModel):
    tenant_name: str = Field(min_length=2, max_length=120)
    tenant_slug: Optional[str] = Field(default=None, min_length=2, max_length=120)
    timezone: str = Field(default="UTC", min_length=2, max_length=64)
    plan: Optional[str] = Field(default="starter", max_length=64)
    owner_full_name: str = Field(min_length=2, max_length=120)
    owner_email: str = Field(min_length=5, max_length=160)
    owner_password: str = Field(min_length=8, max_length=256)


class SaasBootstrapRead(SaasBaseModel):
    tenant: SaasTenantRead
    owner: SaasUserRead
    token: SaasTokenRead


class SaasLoginCreate(SaasBaseModel):
    email: str = Field(min_length=5, max_length=160)
    password: str = Field(min_length=1, max_length=256)
    tenant_slug: Optional[str] = Field(default=None, min_length=2, max_length=120)


class SaasUserCreate(SaasBaseModel):
    full_name: str = Field(min_length=2, max_length=120)
    email: str = Field(min_length=5, max_length=160)
    password: str = Field(min_length=8, max_length=256)
    role: TenantRole
    phone: Optional[str] = Field(default=None, max_length=40)


class SaasPatientTypeCreate(SaasBaseModel):
    name: str = Field(min_length=2, max_length=120)
    slug: Optional[str] = Field(default=None, min_length=2, max_length=120)
    description: Optional[str] = Field(default=None, max_length=500)


class SaasPatientTypeRead(SaasBaseModel):
    id: str
    tenant_id: str
    name: str
    slug: Optional[str] = None
    description: Optional[str] = None
    active: bool
    created_at: datetime


class SaasPatientCreate(SaasBaseModel):
    patient_type_id: str
    medical_record_number: Optional[str] = Field(default=None, max_length=64)
    document_number: Optional[str] = Field(default=None, max_length=64)
    first_name: str = Field(min_length=2, max_length=80)
    last_name: str = Field(min_length=2, max_length=80)
    date_of_birth: Optional[date] = None
    sex: Optional[str] = Field(default=None, max_length=20)
    phone: Optional[str] = Field(default=None, max_length=40)
    email: Optional[str] = Field(default=None, max_length=160)
    address: Optional[str] = Field(default=None, max_length=255)
    emergency_contact_name: Optional[str] = Field(default=None, max_length=120)
    emergency_contact_phone: Optional[str] = Field(default=None, max_length=40)
    allergies: Optional[str] = Field(default=None, max_length=400)
    chronic_conditions: Optional[str] = Field(default=None, max_length=400)
    clinical_summary: Optional[str] = Field(default=None, max_length=1200)
    notes: Optional[str] = Field(default=None, max_length=1200)
    status: PatientStatus = PatientStatus.ACTIVE


class SaasPatientRead(SaasBaseModel):
    id: str
    tenant_id: str
    patient_type_id: str
    patient_type_name: Optional[str] = None
    medical_record_number: str
    document_number: Optional[str] = None
    first_name: str
    last_name: str
    full_name: str
    status: PatientStatus
    last_visit_at: Optional[datetime] = None
    created_at: datetime


class SaasVisitCreate(SaasBaseModel):
    patient_id: str
    reason: Optional[str] = Field(default=None, max_length=500)
    triage_notes: Optional[str] = Field(default=None, max_length=1200)
    clinical_notes: Optional[str] = Field(default=None, max_length=1200)
    vitals_summary: Optional[str] = Field(default=None, max_length=500)
    location: Optional[str] = Field(default=None, max_length=120)
    duration_minutes: Optional[int] = Field(default=None, ge=1, le=1440)
    status: VisitStatus = VisitStatus.CHECKED_IN


class SaasVisitRead(SaasBaseModel):
    id: str
    tenant_id: str
    patient_id: str
    patient_name: str
    clinical_record_id: str
    created_by_user_id: Optional[str] = None
    visited_at: datetime
    reason: Optional[str] = None
    status: VisitStatus
    created_at: datetime


class SaasDashboardPatientTypeCount(SaasBaseModel):
    patient_type_id: str
    patient_type_name: str
    total: int


class SaasDashboardRecentVisit(SaasBaseModel):
    visit_id: str
    patient_id: str
    patient_name: str
    visited_at: datetime
    status: VisitStatus
    reason: Optional[str] = None


class SaasDashboardRead(SaasBaseModel):
    tenant_id: str
    total_users: int
    total_patients: int
    total_patient_types: int
    total_visits: int
    patients_by_type: list[SaasDashboardPatientTypeCount]
    recent_visits: list[SaasDashboardRecentVisit]
    generated_at: datetime
