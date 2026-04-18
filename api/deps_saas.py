"""Convenience re-exports for SaaS auth dependencies."""

from .security_saas import (
    ALGORITHM,
    ACCESS_TOKEN_EXPIRE_MINUTES,
    CurrentUserContext,
    ROLE_ALIASES,
    ROLE_ORDER,
    SECRET_KEY,
    can_manage_role,
    create_access_token,
    get_current_tenant,
    get_current_user,
    get_session,
    hash_password,
    require_roles,
    verify_password,
)

__all__ = [
    "ALGORITHM",
    "ACCESS_TOKEN_EXPIRE_MINUTES",
    "CurrentUserContext",
    "ROLE_ALIASES",
    "ROLE_ORDER",
    "SECRET_KEY",
    "can_manage_role",
    "create_access_token",
    "get_current_tenant",
    "get_current_user",
    "get_session",
    "hash_password",
    "require_roles",
    "verify_password",
]
