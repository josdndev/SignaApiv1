from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy import func, or_
from sqlmodel import Session, select

from .models_saas import (
    AuditAction,
    AuditLog,
    ClinicalRecord,
    ClinicalRecordStatus,
    Membership,
    Patient,
    PatientStatus,
    PatientType,
    Tenant,
    TenantRole,
    User,
    Visit,
)
from .schemas_saas import (
    SaasBootstrapCreate,
    SaasDashboardPatientTypeCount,
    SaasDashboardRead,
    SaasDashboardRecentVisit,
    SaasLoginCreate,
    SaasPatientCreate,
    SaasPatientRead,
    SaasPatientTypeCreate,
    SaasPatientTypeRead,
    SaasUserCreate,
    SaasUserRead,
    SaasVisitCreate,
    SaasVisitRead,
)
from .security_saas import can_manage_role, hash_password, verify_password


def _bad_request(detail: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=detail)


def _not_found(detail: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=detail)


def _conflict(detail: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=detail)


def _unauthorized(detail: str = "Credenciales invalidas") -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )


def _normalize_email(value: str) -> str:
    email = value.strip().lower()
    if "@" not in email or email.startswith("@") or email.endswith("@"):
        raise _bad_request("Email invalido")
    return email


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.strip().lower()).strip("-")
    return slug or "tenant"


def _unique_tenant_slug(session: Session, base_slug: str) -> str:
    candidate = base_slug
    counter = 2
    while session.exec(select(Tenant).where(Tenant.slug == candidate)).first() is not None:
        candidate = f"{base_slug}-{counter}"
        counter += 1
    return candidate


def _to_user_read(user: User, membership: Membership) -> SaasUserRead:
    return SaasUserRead(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        phone=user.phone,
        active=user.active,
        role=membership.role,
        created_at=user.created_at,
    )


def _to_patient_type_read(patient_type: PatientType) -> SaasPatientTypeRead:
    return SaasPatientTypeRead(
        id=patient_type.id,
        tenant_id=patient_type.tenant_id,
        name=patient_type.name,
        slug=patient_type.slug,
        description=patient_type.description,
        active=patient_type.active,
        created_at=patient_type.created_at,
    )


def _to_patient_read(patient: Patient, patient_type_name: Optional[str]) -> SaasPatientRead:
    return SaasPatientRead(
        id=patient.id,
        tenant_id=patient.tenant_id,
        patient_type_id=patient.patient_type_id,
        patient_type_name=patient_type_name,
        medical_record_number=patient.medical_record_number,
        document_number=patient.document_number,
        first_name=patient.first_name,
        last_name=patient.last_name,
        full_name=f"{patient.first_name} {patient.last_name}".strip(),
        status=patient.status,
        last_visit_at=patient.last_visit_at,
        created_at=patient.created_at,
    )


def _to_visit_read(visit: Visit, patient: Patient) -> SaasVisitRead:
    return SaasVisitRead(
        id=visit.id,
        tenant_id=visit.tenant_id,
        patient_id=visit.patient_id,
        patient_name=f"{patient.first_name} {patient.last_name}".strip(),
        clinical_record_id=visit.clinical_record_id,
        created_by_user_id=visit.created_by_user_id,
        visited_at=visit.visited_at,
        reason=visit.reason,
        status=visit.status,
        created_at=visit.created_at,
    )


def _create_audit_log(
    session: Session,
    *,
    tenant_id: str,
    actor_user_id: Optional[str],
    entity_type: str,
    entity_id: str,
    action: AuditAction,
    message: str,
) -> None:
    session.add(
        AuditLog(
            tenant_id=tenant_id,
            actor_user_id=actor_user_id,
            entity_type=entity_type,
            entity_id=entity_id,
            action=action,
            message=message,
        )
    )


def bootstrap_tenant(session: Session, payload: SaasBootstrapCreate) -> tuple[Tenant, User, Membership]:
    tenant_name = payload.tenant_name.strip()
    if not tenant_name:
        raise _bad_request("tenant_name es requerido")

    owner_name = payload.owner_full_name.strip()
    if not owner_name:
        raise _bad_request("owner_full_name es requerido")

    owner_email = _normalize_email(payload.owner_email)
    owner_password = payload.owner_password.strip()
    if len(owner_password) < 8:
        raise _bad_request("owner_password debe tener al menos 8 caracteres")

    if session.exec(select(User).where(User.email == owner_email)).first() is not None:
        raise _conflict("Ya existe un usuario con ese email")

    base_slug = _slugify(payload.tenant_slug or tenant_name)
    tenant_slug = _unique_tenant_slug(session, base_slug)

    tenant = Tenant(
        name=tenant_name,
        slug=tenant_slug,
        timezone=payload.timezone,
        plan=payload.plan,
    )
    session.add(tenant)
    session.flush()

    owner = User(
        email=owner_email,
        full_name=owner_name,
        password_hash=hash_password(owner_password),
        phone=None,
    )
    session.add(owner)
    session.flush()

    membership = Membership(
        tenant_id=tenant.id,
        user_id=owner.id,
        role=TenantRole.OWNER,
        joined_at=datetime.now(timezone.utc),
    )
    session.add(membership)

    _create_audit_log(
        session,
        tenant_id=tenant.id,
        actor_user_id=owner.id,
        entity_type="tenant",
        entity_id=tenant.id,
        action=AuditAction.CREATE,
        message="Tenant bootstrap completed",
    )

    session.commit()
    session.refresh(tenant)
    session.refresh(owner)
    session.refresh(membership)
    return tenant, owner, membership


def authenticate_user(
    session: Session,
    payload: SaasLoginCreate,
) -> tuple[User, Tenant, Membership]:
    email = _normalize_email(payload.email)
    user = session.exec(select(User).where(User.email == email)).first()
    if not user or not user.active or user.is_deleted:
        raise _unauthorized()

    if not verify_password(payload.password, user.password_hash):
        raise _unauthorized()

    membership_query = select(Membership).where(
        Membership.user_id == user.id,
        Membership.active.is_(True),
        Membership.is_deleted.is_(False),
    )

    if payload.tenant_slug:
        tenant = session.exec(select(Tenant).where(Tenant.slug == payload.tenant_slug)).first()
        if tenant is None:
            raise _unauthorized("Tenant no encontrado")
        membership_query = membership_query.where(Membership.tenant_id == tenant.id)

    membership = session.exec(membership_query.order_by(Membership.created_at.asc())).first()
    if membership is None:
        raise _forbidden("Usuario sin membresia activa")

    tenant = session.get(Tenant, membership.tenant_id)
    if not tenant or not tenant.active or tenant.is_deleted:
        raise _forbidden("Tenant inactivo")

    user.last_login_at = datetime.now(timezone.utc)
    _create_audit_log(
        session,
        tenant_id=tenant.id,
        actor_user_id=user.id,
        entity_type="user",
        entity_id=user.id,
        action=AuditAction.LOGIN,
        message="User login",
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    session.refresh(tenant)
    session.refresh(membership)
    return user, tenant, membership


def create_user_for_tenant(
    session: Session,
    *,
    tenant_id: str,
    actor_user_id: str,
    actor_role: TenantRole,
    payload: SaasUserCreate,
) -> tuple[User, Membership]:
    if payload.role == TenantRole.OWNER:
        raise _bad_request("No puedes crear otro owner por este endpoint")
    if not can_manage_role(actor_role, payload.role):
        raise _forbidden("No tienes permisos para crear este rol")

    email = _normalize_email(payload.email)
    if session.exec(select(User).where(User.email == email)).first() is not None:
        raise _conflict("Ya existe un usuario con ese email")

    tenant = session.get(Tenant, tenant_id)
    if tenant is None or tenant.is_deleted:
        raise _not_found("Tenant no encontrado")

    user = User(
        email=email,
        full_name=payload.full_name.strip(),
        password_hash=hash_password(payload.password),
        phone=payload.phone,
    )
    session.add(user)
    session.flush()

    membership = Membership(
        tenant_id=tenant_id,
        user_id=user.id,
        role=payload.role,
        invited_at=datetime.now(timezone.utc),
        joined_at=datetime.now(timezone.utc),
    )
    session.add(membership)

    _create_audit_log(
        session,
        tenant_id=tenant_id,
        actor_user_id=actor_user_id,
        entity_type="membership",
        entity_id=membership.id,
        action=AuditAction.ASSIGN_ROLE,
        message=f"Created user {user.email} with role {payload.role.value}",
    )

    session.commit()
    session.refresh(user)
    session.refresh(membership)
    return user, membership


def list_tenant_users(session: Session, tenant_id: str) -> list[SaasUserRead]:
    rows = session.exec(
        select(User, Membership)
        .join(Membership, Membership.user_id == User.id)
        .where(
            Membership.tenant_id == tenant_id,
            Membership.active.is_(True),
            Membership.is_deleted.is_(False),
            User.active.is_(True),
            User.is_deleted.is_(False),
        )
        .order_by(Membership.role, User.full_name)
    ).all()

    return [_to_user_read(user=row[0], membership=row[1]) for row in rows]


def create_patient_type(
    session: Session,
    *,
    tenant_id: str,
    actor_user_id: str,
    payload: SaasPatientTypeCreate,
) -> PatientType:
    tenant = session.get(Tenant, tenant_id)
    if tenant is None:
        raise _not_found("Tenant no encontrado")

    name = payload.name.strip()
    if not name:
        raise _bad_request("name es requerido")

    slug = _slugify(payload.slug or name)

    existing = session.exec(
        select(PatientType).where(
            PatientType.tenant_id == tenant_id,
            PatientType.name == name,
            PatientType.is_deleted.is_(False),
        )
    ).first()
    if existing is not None:
        raise _conflict("Ya existe un tipo de paciente con ese nombre")

    patient_type = PatientType(
        tenant_id=tenant_id,
        name=name,
        slug=slug,
        description=payload.description,
    )
    session.add(patient_type)

    _create_audit_log(
        session,
        tenant_id=tenant_id,
        actor_user_id=actor_user_id,
        entity_type="patient_type",
        entity_id=patient_type.id,
        action=AuditAction.CREATE,
        message=f"Created patient type {name}",
    )

    session.commit()
    session.refresh(patient_type)
    return patient_type


def list_patient_types(session: Session, tenant_id: str) -> list[SaasPatientTypeRead]:
    patient_types = session.exec(
        select(PatientType)
        .where(
            PatientType.tenant_id == tenant_id,
            PatientType.active.is_(True),
            PatientType.is_deleted.is_(False),
        )
        .order_by(PatientType.name)
    ).all()
    return [_to_patient_type_read(patient_type) for patient_type in patient_types]


def _next_mrn(session: Session, tenant_id: str) -> str:
    total = session.exec(
        select(func.count(Patient.id)).where(
            Patient.tenant_id == tenant_id,
            Patient.is_deleted.is_(False),
        )
    ).one()
    return f"MRN-{int(total) + 1:07d}"


def create_patient(
    session: Session,
    *,
    tenant_id: str,
    actor_user_id: str,
    payload: SaasPatientCreate,
) -> SaasPatientRead:
    patient_type = session.exec(
        select(PatientType).where(
            PatientType.id == payload.patient_type_id,
            PatientType.tenant_id == tenant_id,
            PatientType.active.is_(True),
            PatientType.is_deleted.is_(False),
        )
    ).first()
    if patient_type is None:
        raise _not_found("Tipo de paciente no encontrado para este tenant")

    mrn = payload.medical_record_number or _next_mrn(session, tenant_id)

    if payload.document_number:
        duplicate = session.exec(
            select(Patient).where(
                Patient.tenant_id == tenant_id,
                Patient.document_number == payload.document_number,
                Patient.is_deleted.is_(False),
            )
        ).first()
        if duplicate is not None:
            raise _conflict("Ya existe un paciente con ese documento")

    patient = Patient(
        tenant_id=tenant_id,
        patient_type_id=patient_type.id,
        medical_record_number=mrn,
        document_number=payload.document_number,
        first_name=payload.first_name.strip(),
        last_name=payload.last_name.strip(),
        date_of_birth=payload.date_of_birth,
        sex=payload.sex,
        phone=payload.phone,
        email=payload.email,
        address=payload.address,
        emergency_contact_name=payload.emergency_contact_name,
        emergency_contact_phone=payload.emergency_contact_phone,
        allergies=payload.allergies,
        chronic_conditions=payload.chronic_conditions,
        clinical_summary=payload.clinical_summary,
        notes=payload.notes,
        status=payload.status,
    )
    session.add(patient)

    _create_audit_log(
        session,
        tenant_id=tenant_id,
        actor_user_id=actor_user_id,
        entity_type="patient",
        entity_id=patient.id,
        action=AuditAction.CREATE,
        message=f"Created patient {patient.first_name} {patient.last_name}",
    )

    session.commit()
    session.refresh(patient)
    return _to_patient_read(patient, patient_type.name)


def list_patients(
    session: Session,
    *,
    tenant_id: str,
    patient_type_id: Optional[str],
    status_filter: Optional[str],
    search: Optional[str],
    limit: int,
    offset: int,
) -> list[SaasPatientRead]:
    query = (
        select(Patient, PatientType.name)
        .join(PatientType, Patient.patient_type_id == PatientType.id)
        .where(
            Patient.tenant_id == tenant_id,
            Patient.is_deleted.is_(False),
            PatientType.tenant_id == tenant_id,
        )
    )

    if patient_type_id:
        query = query.where(Patient.patient_type_id == patient_type_id)

    if status_filter:
        try:
            normalized_status = status_filter.strip().lower()
            status_enum = PatientStatus(normalized_status)
            query = query.where(Patient.status == status_enum)
        except ValueError:
            raise _bad_request("status invalido")

    if search:
        term = f"%{search.strip()}%"
        query = query.where(
            or_(
                Patient.first_name.ilike(term),
                Patient.last_name.ilike(term),
                Patient.document_number.ilike(term),
                Patient.medical_record_number.ilike(term),
            )
        )

    rows = session.exec(query.order_by(Patient.created_at.desc()).limit(limit).offset(offset)).all()
    return [_to_patient_read(patient=row[0], patient_type_name=row[1]) for row in rows]


def get_patient(session: Session, *, tenant_id: str, patient_id: str) -> SaasPatientRead:
    row = session.exec(
        select(Patient, PatientType.name)
        .join(PatientType, Patient.patient_type_id == PatientType.id)
        .where(
            Patient.id == patient_id,
            Patient.tenant_id == tenant_id,
            Patient.is_deleted.is_(False),
            PatientType.tenant_id == tenant_id,
        )
    ).first()

    if row is None:
        raise _not_found("Paciente no encontrado")

    return _to_patient_read(patient=row[0], patient_type_name=row[1])


def _get_or_create_open_record(session: Session, *, tenant_id: str, patient: Patient, actor_user_id: str) -> ClinicalRecord:
    record = session.exec(
        select(ClinicalRecord).where(
            ClinicalRecord.tenant_id == tenant_id,
            ClinicalRecord.patient_id == patient.id,
            ClinicalRecord.status == ClinicalRecordStatus.OPEN,
            ClinicalRecord.is_deleted.is_(False),
        )
    ).first()

    if record is not None:
        return record

    counter = session.exec(
        select(func.count(ClinicalRecord.id)).where(ClinicalRecord.tenant_id == tenant_id)
    ).one()
    record = ClinicalRecord(
        tenant_id=tenant_id,
        patient_id=patient.id,
        created_by_user_id=actor_user_id,
        record_number=f"REC-{int(counter) + 1:07d}",
        status=ClinicalRecordStatus.OPEN,
    )
    session.add(record)
    session.flush()
    return record


def create_visit(
    session: Session,
    *,
    tenant_id: str,
    actor_user_id: str,
    payload: SaasVisitCreate,
) -> SaasVisitRead:
    patient = session.exec(
        select(Patient).where(
            Patient.id == payload.patient_id,
            Patient.tenant_id == tenant_id,
            Patient.is_deleted.is_(False),
        )
    ).first()
    if patient is None:
        raise _not_found("Paciente no encontrado")

    record = _get_or_create_open_record(
        session,
        tenant_id=tenant_id,
        patient=patient,
        actor_user_id=actor_user_id,
    )

    visit = Visit(
        tenant_id=tenant_id,
        patient_id=patient.id,
        clinical_record_id=record.id,
        created_by_user_id=actor_user_id,
        reason=payload.reason,
        triage_notes=payload.triage_notes,
        clinical_notes=payload.clinical_notes,
        vitals_summary=payload.vitals_summary,
        location=payload.location,
        duration_minutes=payload.duration_minutes,
        status=payload.status,
        visited_at=datetime.now(timezone.utc),
    )
    session.add(visit)

    patient.last_visit_at = visit.visited_at
    session.add(patient)

    _create_audit_log(
        session,
        tenant_id=tenant_id,
        actor_user_id=actor_user_id,
        entity_type="visit",
        entity_id=visit.id,
        action=AuditAction.CREATE,
        message=f"Created visit for patient {patient.id}",
    )

    session.commit()
    session.refresh(visit)
    session.refresh(patient)
    return _to_visit_read(visit, patient)


def list_visits_for_tenant(
    session: Session,
    *,
    tenant_id: str,
    limit: int,
    offset: int,
) -> list[SaasVisitRead]:
    rows = session.exec(
        select(Visit, Patient)
        .join(Patient, Patient.id == Visit.patient_id)
        .where(
            Visit.tenant_id == tenant_id,
            Visit.is_deleted.is_(False),
            Patient.tenant_id == tenant_id,
            Patient.is_deleted.is_(False),
        )
        .order_by(Visit.visited_at.desc())
        .limit(limit)
        .offset(offset)
    ).all()
    return [_to_visit_read(visit=row[0], patient=row[1]) for row in rows]


def get_dashboard(session: Session, *, tenant_id: str) -> SaasDashboardRead:
    total_users = session.exec(
        select(func.count(Membership.id)).where(
            Membership.tenant_id == tenant_id,
            Membership.active.is_(True),
            Membership.is_deleted.is_(False),
        )
    ).one()

    total_patients = session.exec(
        select(func.count(Patient.id)).where(
            Patient.tenant_id == tenant_id,
            Patient.is_deleted.is_(False),
        )
    ).one()

    total_patient_types = session.exec(
        select(func.count(PatientType.id)).where(
            PatientType.tenant_id == tenant_id,
            PatientType.is_deleted.is_(False),
        )
    ).one()

    total_visits = session.exec(
        select(func.count(Visit.id)).where(
            Visit.tenant_id == tenant_id,
            Visit.is_deleted.is_(False),
        )
    ).one()

    type_rows = session.exec(
        select(PatientType.id, PatientType.name, func.count(Patient.id))
        .join(Patient, Patient.patient_type_id == PatientType.id)
        .where(
            PatientType.tenant_id == tenant_id,
            PatientType.is_deleted.is_(False),
            Patient.is_deleted.is_(False),
        )
        .group_by(PatientType.id, PatientType.name)
        .order_by(func.count(Patient.id).desc())
    ).all()

    patients_by_type = [
        SaasDashboardPatientTypeCount(
            patient_type_id=row[0],
            patient_type_name=row[1],
            total=int(row[2]),
        )
        for row in type_rows
    ]

    recent_rows = session.exec(
        select(Visit, Patient)
        .join(Patient, Patient.id == Visit.patient_id)
        .where(
            Visit.tenant_id == tenant_id,
            Visit.is_deleted.is_(False),
            Patient.is_deleted.is_(False),
        )
        .order_by(Visit.visited_at.desc())
        .limit(10)
    ).all()

    recent_visits = [
        SaasDashboardRecentVisit(
            visit_id=row[0].id,
            patient_id=row[1].id,
            patient_name=f"{row[1].first_name} {row[1].last_name}".strip(),
            visited_at=row[0].visited_at,
            status=row[0].status,
            reason=row[0].reason,
        )
        for row in recent_rows
    ]

    return SaasDashboardRead(
        tenant_id=tenant_id,
        total_users=int(total_users),
        total_patients=int(total_patients),
        total_patient_types=int(total_patient_types),
        total_visits=int(total_visits),
        patients_by_type=patients_by_type,
        recent_visits=recent_visits,
        generated_at=datetime.now(timezone.utc),
    )


def _forbidden(detail: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=detail)
