-- 04_appointments.sql
-- Agenda y citas: seeds y consultas operativas para PostgreSQL.

-- LOAD_QUERIES

-- Seed de statuses de cita por tenant.
INSERT INTO appointment_status (tenant_id, code, name)
VALUES
    ($1, 'scheduled', 'Programada'),
    ($1, 'confirmed', 'Confirmada'),
    ($1, 'checked_in', 'Registrada'),
    ($1, 'completed', 'Completada'),
    ($1, 'cancelled', 'Cancelada'),
    ($1, 'no_show', 'No asistio'),
    ($1, 'rescheduled', 'Reprogramada')
ON CONFLICT (tenant_id, code) DO UPDATE
SET name = EXCLUDED.name;

-- Seed de tipos de cita por tenant.
INSERT INTO appointment_types (tenant_id, code, name, duration_minutes)
VALUES
    ($1, 'general_consultation', 'Consulta general', 20),
    ($1, 'follow_up', 'Control / seguimiento', 15),
    ($1, 'emergency', 'Emergencia', 10),
    ($1, 'telemedicine', 'Teleconsulta', 20),
    ($1, 'procedure', 'Procedimiento', 45),
    ($1, 'nursing', 'Enfermeria', 15)
ON CONFLICT (tenant_id, code) DO UPDATE
SET name = EXCLUDED.name,
    duration_minutes = EXCLUDED.duration_minutes;

-- OPERATIONAL_QUERIES

-- Disponibilidad de agenda del medico.
-- $1 tenant_id
-- $2 doctor_user_id
-- $3 branch_id (nullable)
-- $4 target_date (date o timestamptz)
SELECT
    s.id AS slot_id,
    s.tenant_id,
    s.doctor_user_id,
    s.branch_id,
    s.slot_start,
    s.slot_end,
    s.is_available,
    a.id AS appointment_id,
    a.patient_id,
    p.first_name,
    p.last_name,
    at.code AS appointment_type_code,
    at.name AS appointment_type_name,
    st.code AS status_code,
    st.name AS status_name,
    a.reason_description
FROM appointment_slots s
JOIN doctor_schedules ds
    ON ds.tenant_id = s.tenant_id
   AND ds.doctor_user_id = s.doctor_user_id
   AND (ds.branch_id IS NULL OR ds.branch_id IS NOT DISTINCT FROM s.branch_id)
   AND ds.weekday = EXTRACT(ISODOW FROM s.slot_start)::SMALLINT
   AND s.slot_start::TIME >= ds.start_time
   AND s.slot_end::TIME <= ds.end_time
LEFT JOIN appointments a
    ON a.tenant_id = s.tenant_id
   AND a.doctor_id = s.doctor_user_id
   AND a.appointment_date = s.slot_start
   AND (a.branch_id IS NOT DISTINCT FROM s.branch_id)
LEFT JOIN patients p
    ON p.id = a.patient_id
LEFT JOIN appointment_types at
    ON at.id = a.appointment_type_id
LEFT JOIN appointment_status st
    ON st.id = a.status_id
WHERE s.tenant_id = $1
  AND s.doctor_user_id = $2
  AND ($3::UUID IS NULL OR s.branch_id = $3)
  AND s.slot_start >= date_trunc('day', $4::timestamptz)
  AND s.slot_start < date_trunc('day', $4::timestamptz) + INTERVAL '1 day'
  AND s.is_available = TRUE
  AND NOT EXISTS (
      SELECT 1
      FROM holidays_calendar h
      WHERE h.tenant_id = s.tenant_id
        AND h.holiday_date = s.slot_start::DATE
        AND (h.branch_id IS NULL OR h.branch_id IS NOT DISTINCT FROM s.branch_id)
  )
  AND a.id IS NULL
ORDER BY s.slot_start;

-- Creacion de cita.
-- $1 tenant_id
-- $2 patient_id
-- $3 doctor_user_id
-- $4 branch_id (nullable)
-- $5 appointment_type_code
-- $6 appointment_date (timestamptz)
-- $7 reason_description
-- $8 status_code (nullable, default scheduled)
WITH appointment_type_choice AS (
    SELECT id
    FROM appointment_types
    WHERE tenant_id = $1
      AND code = $5
    LIMIT 1
),
status_choice AS (
    SELECT id
    FROM appointment_status
    WHERE tenant_id = $1
      AND code = COALESCE($8, 'scheduled')
    LIMIT 1
),
target_slot AS (
    SELECT s.id, s.slot_start
    FROM appointment_slots s
    WHERE s.tenant_id = $1
      AND s.doctor_user_id = $3
      AND (s.branch_id IS NOT DISTINCT FROM $4)
      AND s.slot_start = $6::timestamptz
      AND s.is_available = TRUE
    FOR UPDATE
),
inserted_appointment AS (
    INSERT INTO appointments (
        tenant_id,
        patient_id,
        doctor_id,
        branch_id,
        appointment_type_id,
        status_id,
        appointment_date,
        reason_description
    )
    SELECT
        $1,
        $2,
        $3,
        $4,
        (SELECT id FROM appointment_type_choice),
        (SELECT id FROM status_choice),
        ts.slot_start,
        $7
    FROM target_slot ts
    WHERE EXISTS (SELECT 1 FROM appointment_type_choice)
      AND EXISTS (SELECT 1 FROM status_choice)
    RETURNING *
),
updated_slot AS (
    UPDATE appointment_slots s
    SET is_available = FALSE
    FROM inserted_appointment ia
    JOIN target_slot ts
      ON ts.slot_start = ia.appointment_date
    WHERE s.id = ts.id
    RETURNING s.id
)
SELECT
    ia.id,
    ia.tenant_id,
    ia.patient_id,
    ia.doctor_id,
    ia.branch_id,
    ia.appointment_type_id,
    ia.status_id,
    ia.appointment_date,
    ia.reason_description,
    ia.created_at,
    ia.updated_at
FROM inserted_appointment ia
LEFT JOIN updated_slot us ON TRUE;

-- Cancelacion de cita.
-- $1 tenant_id
-- $2 appointment_id
WITH cancelled_status AS (
    SELECT id
    FROM appointment_status
    WHERE tenant_id = $1
      AND code = 'cancelled'
    LIMIT 1
),
updated_appointment AS (
    UPDATE appointments a
    SET status_id = (SELECT id FROM cancelled_status),
        updated_at = NOW()
    WHERE a.tenant_id = $1
      AND a.id = $2
      AND EXISTS (SELECT 1 FROM cancelled_status)
    RETURNING a.*
),
released_slot AS (
    UPDATE appointment_slots s
    SET is_available = TRUE
    FROM updated_appointment a
    WHERE s.tenant_id = a.tenant_id
      AND s.doctor_user_id = a.doctor_id
      AND s.slot_start = a.appointment_date
      AND (s.branch_id IS NOT DISTINCT FROM a.branch_id)
    RETURNING s.id
)
SELECT
    ua.id,
    ua.tenant_id,
    ua.patient_id,
    ua.doctor_id,
    ua.branch_id,
    ua.appointment_type_id,
    ua.status_id,
    ua.appointment_date,
    ua.reason_description,
    ua.created_at,
    ua.updated_at
FROM updated_appointment ua
LEFT JOIN released_slot rs ON TRUE;

-- No-show de cita.
-- $1 tenant_id
-- $2 appointment_id
WITH no_show_status AS (
    SELECT id
    FROM appointment_status
    WHERE tenant_id = $1
      AND code = 'no_show'
    LIMIT 1
),
updated_appointment AS (
    UPDATE appointments a
    SET status_id = (SELECT id FROM no_show_status),
        updated_at = NOW()
    WHERE a.tenant_id = $1
      AND a.id = $2
      AND EXISTS (SELECT 1 FROM no_show_status)
    RETURNING a.*
)
SELECT
    ua.id,
    ua.tenant_id,
    ua.patient_id,
    ua.doctor_id,
    ua.branch_id,
    ua.appointment_type_id,
    ua.status_id,
    ua.appointment_date,
    ua.reason_description,
    ua.created_at,
    ua.updated_at
FROM updated_appointment ua;

-- Lista de espera.
-- $1 tenant_id
-- $2 patient_id
-- $3 appointment_type_code (nullable)
-- $4 priority (nullable, default 3)
-- $5 notes (nullable)
INSERT INTO waiting_list (
    tenant_id,
    patient_id,
    appointment_type_id,
    priority,
    notes
)
VALUES (
    $1,
    $2,
    (
        SELECT id
        FROM appointment_types
        WHERE tenant_id = $1
          AND code = $3
        LIMIT 1
    ),
    COALESCE($4::SMALLINT, 3),
    $5
)
RETURNING
    id,
    tenant_id,
    patient_id,
    appointment_type_id,
    priority,
    requested_at,
    status,
    notes,
    created_at;

-- Agenda diaria del medico.
-- $1 tenant_id
-- $2 doctor_user_id
-- $3 branch_id (nullable)
-- $4 agenda_date (date o timestamptz)
SELECT
    s.id AS slot_id,
    s.tenant_id,
    s.doctor_user_id,
    s.branch_id,
    s.slot_start,
    s.slot_end,
    s.is_available,
    a.id AS appointment_id,
    a.patient_id,
    p.first_name,
    p.last_name,
    at.code AS appointment_type_code,
    at.name AS appointment_type_name,
    st.code AS status_code,
    st.name AS status_name,
    a.reason_description
FROM appointment_slots s
LEFT JOIN appointments a
    ON a.tenant_id = s.tenant_id
   AND a.doctor_id = s.doctor_user_id
   AND a.appointment_date = s.slot_start
   AND (a.branch_id IS NOT DISTINCT FROM s.branch_id)
LEFT JOIN patients p
    ON p.id = a.patient_id
LEFT JOIN appointment_types at
    ON at.id = a.appointment_type_id
LEFT JOIN appointment_status st
    ON st.id = a.status_id
WHERE s.tenant_id = $1
  AND s.doctor_user_id = $2
  AND ($3::UUID IS NULL OR s.branch_id = $3)
  AND s.slot_start >= date_trunc('day', $4::timestamptz)
  AND s.slot_start < date_trunc('day', $4::timestamptz) + INTERVAL '1 day'
  AND NOT EXISTS (
      SELECT 1
      FROM holidays_calendar h
      WHERE h.tenant_id = s.tenant_id
        AND h.holiday_date = s.slot_start::DATE
        AND (h.branch_id IS NULL OR h.branch_id IS NOT DISTINCT FROM s.branch_id)
  )
ORDER BY s.slot_start;
