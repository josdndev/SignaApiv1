-- ============================================================================
-- Module: IAM
-- File: db/loaders/01_iam.sql
-- Target: PostgreSQL
-- Purpose: base seed for IAM plus operational query pack
-- Placeholders: :tenant_id, :user_id, :role_id, :permission_id, etc.
-- Notes:
-- - Catalog inserts use ON CONFLICT DO NOTHING
-- - No real secrets are stored here
-- - The seed assumes the tenant already exists
-- ============================================================================

-- LOAD_QUERIES

-- 1) Base roles for a tenant
INSERT INTO roles (
    tenant_id,
    name,
    code,
    description,
    is_system
)
VALUES
    (:tenant_id, 'Owner', 'owner', 'Tenant owner with full access', TRUE),
    (:tenant_id, 'Admin', 'admin', 'Tenant administrator with full access', TRUE),
    (:tenant_id, 'Doctor', 'doctor', 'Clinical user with limited operational access', TRUE),
    (:tenant_id, 'Nurse', 'nurse', 'Nursing user with limited operational access', TRUE),
    (:tenant_id, 'Receptionist', 'receptionist', 'Front desk user with intake access', TRUE),
    (:tenant_id, 'Analyst', 'analyst', 'Read-only analytical user', TRUE)
ON CONFLICT (tenant_id, code) DO NOTHING;

-- 2) Base permissions for IAM
INSERT INTO permissions (
    tenant_id,
    module,
    action,
    code
)
VALUES
    (:tenant_id, 'iam', 'user_create', 'iam.user.create'),
    (:tenant_id, 'iam', 'user_read', 'iam.user.read'),
    (:tenant_id, 'iam', 'user_update', 'iam.user.update'),
    (:tenant_id, 'iam', 'user_deactivate', 'iam.user.deactivate'),
    (:tenant_id, 'iam', 'role_read', 'iam.role.read'),
    (:tenant_id, 'iam', 'role_assign', 'iam.role.assign'),
    (:tenant_id, 'iam', 'role_revoke', 'iam.role.revoke'),
    (:tenant_id, 'iam', 'permission_read', 'iam.permission.read'),
    (:tenant_id, 'iam', 'audit_read', 'iam.audit.read'),
    (:tenant_id, 'iam', 'login_read', 'iam.login.read'),
    (:tenant_id, 'iam', 'login_record', 'iam.login.record'),
    (:tenant_id, 'iam', 'login_failed', 'iam.login.failed'),
    (:tenant_id, 'iam', 'mfa_read', 'iam.mfa.read'),
    (:tenant_id, 'iam', 'mfa_update', 'iam.mfa.update'),
    (:tenant_id, 'iam', 'password_reset', 'iam.password.reset')
ON CONFLICT (tenant_id, code) DO NOTHING;

-- 3) Role-permission mappings
WITH role_permission_map (role_code, permission_code) AS (
    VALUES
        ('owner', 'iam.user.create'),
        ('owner', 'iam.user.read'),
        ('owner', 'iam.user.update'),
        ('owner', 'iam.user.deactivate'),
        ('owner', 'iam.role.read'),
        ('owner', 'iam.role.assign'),
        ('owner', 'iam.role.revoke'),
        ('owner', 'iam.permission.read'),
        ('owner', 'iam.audit.read'),
        ('owner', 'iam.login.read'),
        ('owner', 'iam.login.record'),
        ('owner', 'iam.login.failed'),
        ('owner', 'iam.mfa.read'),
        ('owner', 'iam.mfa.update'),
        ('owner', 'iam.password.reset'),

        ('admin', 'iam.user.create'),
        ('admin', 'iam.user.read'),
        ('admin', 'iam.user.update'),
        ('admin', 'iam.user.deactivate'),
        ('admin', 'iam.role.read'),
        ('admin', 'iam.role.assign'),
        ('admin', 'iam.role.revoke'),
        ('admin', 'iam.permission.read'),
        ('admin', 'iam.audit.read'),
        ('admin', 'iam.login.read'),
        ('admin', 'iam.login.record'),
        ('admin', 'iam.login.failed'),
        ('admin', 'iam.mfa.read'),
        ('admin', 'iam.mfa.update'),
        ('admin', 'iam.password.reset'),

        ('doctor', 'iam.user.read'),
        ('doctor', 'iam.audit.read'),
        ('doctor', 'iam.login.read'),
        ('doctor', 'iam.mfa.read'),

        ('nurse', 'iam.user.read'),
        ('nurse', 'iam.audit.read'),
        ('nurse', 'iam.login.read'),
        ('nurse', 'iam.mfa.read'),

        ('receptionist', 'iam.user.read'),
        ('receptionist', 'iam.login.read'),

        ('analyst', 'iam.user.read'),
        ('analyst', 'iam.audit.read'),
        ('analyst', 'iam.login.read')
)
INSERT INTO role_permissions (
    tenant_id,
    role_id,
    permission_id
)
SELECT
    :tenant_id,
    r.id,
    p.id
FROM role_permission_map rpm
JOIN roles r
    ON r.tenant_id = :tenant_id
   AND r.code = rpm.role_code
JOIN permissions p
    ON p.tenant_id = :tenant_id
   AND p.code = rpm.permission_code
ON CONFLICT (tenant_id, role_id, permission_id) DO NOTHING;

-- 4) Example initial admin user
INSERT INTO users (
    tenant_id,
    username,
    email,
    password_hash,
    is_active
)
VALUES (
    :tenant_id,
    :admin_username,
    :admin_email,
    :admin_password_hash,
    TRUE
)
ON CONFLICT DO NOTHING;

-- 5) Assign the admin role to the example user
INSERT INTO user_roles (
    tenant_id,
    user_id,
    role_id,
    assigned_by
)
SELECT
    :tenant_id,
    u.id,
    r.id,
    :assigned_by_user_id
FROM users u
JOIN roles r
    ON r.tenant_id = u.tenant_id
   AND r.code = 'admin'
WHERE u.tenant_id = :tenant_id
  AND u.email = :admin_email
ON CONFLICT (tenant_id, user_id, role_id) DO NOTHING;

-- OPERATIONAL_QUERIES

-- 1) Get a user with his/her active roles
SELECT
    u.id,
    u.tenant_id,
    u.username,
    u.email,
    u.is_active,
    u.last_login_at,
    u.created_at,
    u.updated_at,
    COALESCE(
        string_agg(DISTINCT r.code, ',' ORDER BY r.code),
        ''
    ) AS role_codes
FROM users u
LEFT JOIN user_roles ur
    ON ur.tenant_id = u.tenant_id
   AND ur.user_id = u.id
LEFT JOIN roles r
    ON r.tenant_id = ur.tenant_id
   AND r.id = ur.role_id
WHERE u.tenant_id = :tenant_id
  AND u.id = :user_id
GROUP BY
    u.id,
    u.tenant_id,
    u.username,
    u.email,
    u.is_active,
    u.last_login_at,
    u.created_at,
    u.updated_at;

-- 2) List users for a tenant with roles
SELECT
    u.id,
    u.username,
    u.email,
    u.is_active,
    u.last_login_at,
    u.created_at,
    COALESCE(
        string_agg(DISTINCT r.code, ',' ORDER BY r.code),
        ''
    ) AS role_codes
FROM users u
LEFT JOIN user_roles ur
    ON ur.tenant_id = u.tenant_id
   AND ur.user_id = u.id
LEFT JOIN roles r
    ON r.tenant_id = ur.tenant_id
   AND r.id = ur.role_id
WHERE u.tenant_id = :tenant_id
  AND u.is_active IS TRUE
GROUP BY
    u.id,
    u.username,
    u.email,
    u.is_active,
    u.last_login_at,
    u.created_at
ORDER BY u.created_at DESC
LIMIT :limit
OFFSET :offset;

-- 3) Get all roles for a tenant
SELECT
    id,
    tenant_id,
    name,
    code,
    description,
    is_system,
    created_at,
    updated_at
FROM roles
WHERE tenant_id = :tenant_id
ORDER BY code;

-- 4) Get all permissions for a tenant
SELECT
    id,
    tenant_id,
    module,
    action,
    code,
    created_at
FROM permissions
WHERE tenant_id = :tenant_id
ORDER BY module, action;

-- 5) Get permissions by role code
SELECT
    p.id,
    p.module,
    p.action,
    p.code,
    p.created_at
FROM roles r
JOIN role_permissions rp
    ON rp.tenant_id = r.tenant_id
   AND rp.role_id = r.id
JOIN permissions p
    ON p.tenant_id = rp.tenant_id
   AND p.id = rp.permission_id
WHERE r.tenant_id = :tenant_id
  AND r.code = :role_code
ORDER BY p.module, p.action;

-- 6) Get effective permissions for a user
SELECT DISTINCT
    p.id,
    p.module,
    p.action,
    p.code
FROM users u
JOIN user_roles ur
    ON ur.tenant_id = u.tenant_id
   AND ur.user_id = u.id
JOIN role_permissions rp
    ON rp.tenant_id = u.tenant_id
   AND rp.role_id = ur.role_id
JOIN permissions p
    ON p.tenant_id = rp.tenant_id
   AND p.id = rp.permission_id
WHERE u.tenant_id = :tenant_id
  AND u.id = :user_id
  AND u.is_active IS TRUE
ORDER BY p.module, p.action;

-- 7) Assign a role to a user
INSERT INTO user_roles (
    tenant_id,
    user_id,
    role_id,
    assigned_by
)
VALUES (
    :tenant_id,
    :user_id,
    :role_id,
    :assigned_by_user_id
)
ON CONFLICT (tenant_id, user_id, role_id) DO NOTHING;

-- 8) Revoke a role from a user
DELETE FROM user_roles
WHERE tenant_id = :tenant_id
  AND user_id = :user_id
  AND role_id = :role_id;

-- 9) Update last login timestamp after a successful login
UPDATE users
SET last_login_at = NOW(),
    updated_at = NOW()
WHERE tenant_id = :tenant_id
  AND id = :user_id;

-- 10) Record a successful login event
INSERT INTO user_logs (
    tenant_id,
    user_id,
    event_type,
    ip_address,
    user_agent,
    details
)
VALUES (
    :tenant_id,
    :user_id,
    'login',
    :ip_address,
    :user_agent,
    jsonb_build_object(
        'status', 'success',
        'source', :source,
        'tenant_id', :tenant_id
    )
);

-- 11) Record a failed login event
INSERT INTO user_logs (
    tenant_id,
    user_id,
    event_type,
    ip_address,
    user_agent,
    details
)
VALUES (
    :tenant_id,
    :user_id,
    'login_failed',
    :ip_address,
    :user_agent,
    jsonb_build_object(
        'status', 'failed',
        'reason', :reason,
        'source', :source,
        'tenant_id', :tenant_id
    )
);

-- 12) Tenant audit trail for a user or actor
SELECT
    ul.id,
    ul.tenant_id,
    ul.user_id,
    ul.event_type,
    ul.ip_address,
    ul.user_agent,
    ul.details,
    ul.created_at
FROM user_logs ul
WHERE ul.tenant_id = :tenant_id
  AND (:user_id IS NULL OR ul.user_id = :user_id)
ORDER BY ul.created_at DESC
LIMIT :limit
OFFSET :offset;

-- 13) Recent login activity for a tenant
SELECT
    ul.id,
    ul.user_id,
    u.email,
    u.username,
    ul.event_type,
    ul.ip_address,
    ul.user_agent,
    ul.details,
    ul.created_at
FROM user_logs ul
LEFT JOIN users u
    ON u.tenant_id = ul.tenant_id
   AND u.id = ul.user_id
WHERE ul.tenant_id = :tenant_id
  AND ul.event_type IN ('login', 'login_failed')
ORDER BY ul.created_at DESC
LIMIT :limit
OFFSET :offset;

-- 14) Last successful login per user
SELECT
    ul.user_id,
    max(ul.created_at) AS last_successful_login_at
FROM user_logs ul
WHERE ul.tenant_id = :tenant_id
  AND ul.event_type = 'login'
  AND COALESCE(ul.details ->> 'status', '') = 'success'
GROUP BY ul.user_id
ORDER BY last_successful_login_at DESC;

-- 15) Count failed login attempts within a time window
SELECT
    ul.user_id,
    count(*) AS failed_login_attempts
FROM user_logs ul
WHERE ul.tenant_id = :tenant_id
  AND ul.event_type = 'login_failed'
  AND ul.created_at >= :from_ts
  AND ul.created_at < :to_ts
GROUP BY ul.user_id
ORDER BY failed_login_attempts DESC, ul.user_id;
