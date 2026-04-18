from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Callable, Optional

import bcrypt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from sqlmodel import Session, select

from .db import get_session
from .models_saas import Membership, ROLE_HIERARCHY, Tenant, TenantRole, User


ROLE_ALIASES = {
    "clinician": "doctor",
    "staff": "receptionist",
}


def _normalize_role(role: Any) -> Optional[str]:
    if role is None:
        return None
    if isinstance(role, Enum):
        role = role.value
    value = str(role).strip().lower()
    if not value:
        return None
    return ROLE_ALIASES.get(value, value)


ROLE_ORDER = {role.value: rank for role, rank in ROLE_HIERARCHY.items()}


SECRET_KEY = os.getenv("SAAS_SECRET_KEY") or os.getenv("SECRET_KEY") or "dev-only-secret-change-me"
ALGORITHM = os.getenv("SAAS_ALGORITHM") or os.getenv("ALGORITHM") or "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(
    os.getenv("SAAS_ACCESS_TOKEN_EXPIRE_MINUTES")
    or os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES")
    or "30"
)


oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/saas/auth/login")


@dataclass
class CurrentUserContext:
    user: User
    tenant: Tenant
    membership: Membership

    @property
    def id(self) -> str:
        return self.user.id

    @property
    def tenant_id(self) -> str:
        return self.tenant.id

    @property
    def role(self) -> TenantRole:
        return self.membership.role


def _unauthorized(detail: str = "Credenciales invalidas") -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )


def _forbidden(detail: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=detail)


def hash_password(password: str) -> str:
    if not password:
        raise ValueError("password is required")
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    if not password or not password_hash:
        return False
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except ValueError:
        return False


def create_access_token(
    *,
    subject: str,
    tenant_id: str,
    role: str,
    expires_delta: Optional[timedelta] = None,
) -> str:
    normalized_role = _normalize_role(role)
    if not subject or not tenant_id or not normalized_role:
        raise ValueError("subject, tenant_id and role are required")

    payload = {
        "sub": str(subject),
        "tenant_id": str(tenant_id),
        "role": normalized_role,
        "exp": datetime.now(timezone.utc)
        + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def _get_membership(session: Session, user_id: str, tenant_id: str) -> Optional[Membership]:
    return session.exec(
        select(Membership).where(
            Membership.user_id == user_id,
            Membership.tenant_id == tenant_id,
        )
    ).first()


def get_current_user(
    token: str = Depends(oauth2_scheme),
    session: Session = Depends(get_session),
) -> CurrentUserContext:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError as exc:
        raise _unauthorized() from exc

    user_id = payload.get("sub")
    tenant_id = payload.get("tenant_id")
    token_role = _normalize_role(payload.get("role"))

    if not user_id or not tenant_id or not token_role:
        raise _unauthorized()

    user = session.get(User, str(user_id))
    if not user or not user.active or user.is_deleted:
        raise _unauthorized("Usuario invalido o inactivo")

    tenant = session.get(Tenant, str(tenant_id))
    if not tenant or not tenant.active or tenant.is_deleted:
        raise _forbidden("Tenant inactivo")

    membership = _get_membership(session, user.id, tenant.id)
    if not membership or not membership.active or membership.is_deleted:
        raise _forbidden("Membresia inactiva")

    membership_role = _normalize_role(membership.role)
    if membership_role != token_role:
        raise _unauthorized("Token desactualizado")

    return CurrentUserContext(user=user, tenant=tenant, membership=membership)


def get_current_tenant(current_user: CurrentUserContext = Depends(get_current_user)) -> Tenant:
    return current_user.tenant


def can_manage_role(actor_role: Any, target_role: Any) -> bool:
    actor = _normalize_role(actor_role)
    target = _normalize_role(target_role)
    if actor is None or target is None:
        return False
    return ROLE_ORDER.get(actor, 0) > ROLE_ORDER.get(target, 0)


def require_roles(*allowed_roles: str) -> Callable[..., CurrentUserContext]:
    allowed = {_normalize_role(role) for role in allowed_roles}

    def _dependency(current_user: CurrentUserContext = Depends(get_current_user)) -> CurrentUserContext:
        current_role = _normalize_role(current_user.role)
        if None in allowed:
            allowed.discard(None)
        if allowed and current_role not in allowed:
            raise _forbidden("No tienes permisos para esta accion")
        return current_user

    return _dependency
