from __future__ import annotations

from fastapi import APIRouter, Depends, Query, status
from sqlmodel import Session

from .db import get_session
from .schemas_saas import (
    SaasBootstrapCreate,
    SaasBootstrapRead,
    SaasDashboardRead,
    SaasLoginCreate,
    SaasPatientCreate,
    SaasPatientRead,
    SaasPatientTypeCreate,
    SaasPatientTypeRead,
    SaasTokenRead,
    SaasTenantRead,
    SaasUserCreate,
    SaasUserRead,
    SaasVisitCreate,
    SaasVisitRead,
)
from .security_saas import create_access_token, get_current_user, require_roles
from .services_saas import (
    authenticate_user,
    bootstrap_tenant,
    create_patient,
    create_patient_type,
    create_user_for_tenant,
    create_visit,
    get_dashboard,
    get_patient,
    list_patient_types,
    list_patients,
    list_tenant_users,
    list_visits_for_tenant,
)

router = APIRouter(prefix="/saas", tags=["saas"])


@router.post("/bootstrap", response_model=SaasBootstrapRead, status_code=status.HTTP_201_CREATED)
def bootstrap_saas(payload: SaasBootstrapCreate, session: Session = Depends(get_session)):
    tenant, owner, membership = bootstrap_tenant(session, payload)

    tenant_read = SaasTenantRead(
        id=tenant.id,
        name=tenant.name,
        slug=tenant.slug,
        timezone=tenant.timezone,
        plan=tenant.plan,
        active=tenant.active,
        created_at=tenant.created_at,
    )
    owner_read = SaasUserRead(
        id=owner.id,
        email=owner.email,
        full_name=owner.full_name,
        phone=owner.phone,
        active=owner.active,
        role=membership.role,
        created_at=owner.created_at,
    )

    token = create_access_token(
        subject=owner.id,
        tenant_id=tenant.id,
        role=membership.role.value,
    )

    return SaasBootstrapRead(
        tenant=tenant_read,
        owner=owner_read,
        token=SaasTokenRead(access_token=token, token_type="bearer", tenant=tenant_read, user=owner_read),
    )


@router.post("/auth/login", response_model=SaasTokenRead)
def login(payload: SaasLoginCreate, session: Session = Depends(get_session)):
    user, tenant, membership = authenticate_user(session, payload)

    tenant_read = SaasTenantRead(
        id=tenant.id,
        name=tenant.name,
        slug=tenant.slug,
        timezone=tenant.timezone,
        plan=tenant.plan,
        active=tenant.active,
        created_at=tenant.created_at,
    )
    user_read = SaasUserRead(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        phone=user.phone,
        active=user.active,
        role=membership.role,
        created_at=user.created_at,
    )

    token = create_access_token(
        subject=user.id,
        tenant_id=tenant.id,
        role=membership.role.value,
    )

    return SaasTokenRead(access_token=token, token_type="bearer", tenant=tenant_read, user=user_read)


@router.post("/users", response_model=SaasUserRead, status_code=status.HTTP_201_CREATED)
def create_user(
    payload: SaasUserCreate,
    current_user=Depends(require_roles("owner", "admin")),
    session: Session = Depends(get_session),
):
    user, membership = create_user_for_tenant(
        session,
        tenant_id=current_user.tenant_id,
        actor_user_id=current_user.id,
        actor_role=current_user.role,
        payload=payload,
    )

    return SaasUserRead(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        phone=user.phone,
        active=user.active,
        role=membership.role,
        created_at=user.created_at,
    )


@router.get("/users", response_model=list[SaasUserRead])
def read_users(
    _: object = Depends(require_roles("owner", "admin")),
    current_user=Depends(get_current_user),
    session: Session = Depends(get_session),
):
    return list_tenant_users(session, current_user.tenant_id)


@router.post("/patient-types", response_model=SaasPatientTypeRead, status_code=status.HTTP_201_CREATED)
def create_patient_type_endpoint(
    payload: SaasPatientTypeCreate,
    _: object = Depends(require_roles("owner", "admin")),
    current_user=Depends(get_current_user),
    session: Session = Depends(get_session),
):
    patient_type = create_patient_type(
        session,
        tenant_id=current_user.tenant_id,
        actor_user_id=current_user.id,
        payload=payload,
    )
    return SaasPatientTypeRead(
        id=patient_type.id,
        tenant_id=patient_type.tenant_id,
        name=patient_type.name,
        slug=patient_type.slug,
        description=patient_type.description,
        active=patient_type.active,
        created_at=patient_type.created_at,
    )


@router.get("/patient-types", response_model=list[SaasPatientTypeRead])
def read_patient_types(
    current_user=Depends(get_current_user),
    session: Session = Depends(get_session),
):
    return list_patient_types(session, current_user.tenant_id)


@router.post("/patients", response_model=SaasPatientRead, status_code=status.HTTP_201_CREATED)
def create_patient_endpoint(
    payload: SaasPatientCreate,
    current_user=Depends(require_roles("owner", "admin", "doctor", "nurse", "clinician")),
    session: Session = Depends(get_session),
):
    return create_patient(
        session,
        tenant_id=current_user.tenant_id,
        actor_user_id=current_user.id,
        payload=payload,
    )


@router.get("/patients", response_model=list[SaasPatientRead])
def read_patients(
    patient_type_id: str | None = Query(default=None),
    status_filter: str | None = Query(default=None, alias="status"),
    search: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    current_user=Depends(get_current_user),
    session: Session = Depends(get_session),
):
    return list_patients(
        session,
        tenant_id=current_user.tenant_id,
        patient_type_id=patient_type_id,
        status_filter=status_filter,
        search=search,
        limit=limit,
        offset=offset,
    )


@router.get("/patients/{patient_id}", response_model=SaasPatientRead)
def read_patient(
    patient_id: str,
    current_user=Depends(get_current_user),
    session: Session = Depends(get_session),
):
    return get_patient(session, tenant_id=current_user.tenant_id, patient_id=patient_id)


@router.post("/visits", response_model=SaasVisitRead, status_code=status.HTTP_201_CREATED)
def create_visit_endpoint(
    payload: SaasVisitCreate,
    current_user=Depends(require_roles("owner", "admin", "doctor", "nurse", "clinician")),
    session: Session = Depends(get_session),
):
    return create_visit(
        session,
        tenant_id=current_user.tenant_id,
        actor_user_id=current_user.id,
        payload=payload,
    )


@router.get("/visits", response_model=list[SaasVisitRead])
def read_visits(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    current_user=Depends(get_current_user),
    session: Session = Depends(get_session),
):
    return list_visits_for_tenant(
        session,
        tenant_id=current_user.tenant_id,
        limit=limit,
        offset=offset,
    )


@router.get("/dashboard", response_model=SaasDashboardRead)
def read_dashboard(
    current_user=Depends(get_current_user),
    session: Session = Depends(get_session),
):
    return get_dashboard(session, tenant_id=current_user.tenant_id)
