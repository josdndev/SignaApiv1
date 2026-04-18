-- LOAD_QUERIES

-- Sede base
INSERT INTO hospital_branches (
    id,
    tenant_id,
    code,
    name,
    address,
    phone,
    is_active
)
VALUES (
    :branch_id,
    :tenant_id,
    'BR-CENTRAL',
    'Sede Central',
    'Av. Principal de Salud, Caracas',
    '+58 212 555 0100',
    TRUE
)
ON CONFLICT (tenant_id, code)
DO UPDATE SET
    name = EXCLUDED.name,
    address = EXCLUDED.address,
    phone = EXCLUDED.phone,
    is_active = EXCLUDED.is_active,
    updated_at = NOW();

-- Catlogos base
INSERT INTO bed_types (
    tenant_id,
    code,
    name,
    description
)
VALUES
    (:tenant_id, 'GEN', 'General', 'Cama general para hospitalizacion'),
    (:tenant_id, 'UCI', 'UCI', 'Cama para cuidados intensivos'),
    (:tenant_id, 'PED', 'Pediatrica', 'Cama para pacientes pediatricos')
ON CONFLICT (tenant_id, code)
DO UPDATE SET
    name = EXCLUDED.name,
    description = EXCLUDED.description;

-- Departamentos
INSERT INTO departments (
    tenant_id,
    branch_id,
    code,
    name
)
SELECT
    :tenant_id,
    hb.id,
    dept.code,
    dept.name
FROM hospital_branches hb
CROSS JOIN (
    VALUES
        ('EMER', 'Emergencias'),
        ('UCI', 'Unidad de Cuidados Intensivos'),
        ('HOSP', 'Hospitalizacion'),
        ('DIAG', 'Imagenologia')
) AS dept(code, name)
WHERE hb.tenant_id = :tenant_id
  AND hb.code = 'BR-CENTRAL'
ON CONFLICT (tenant_id, code)
DO UPDATE SET
    branch_id = EXCLUDED.branch_id,
    name = EXCLUDED.name;

-- Pisos
INSERT INTO floors (
    tenant_id,
    branch_id,
    floor_number,
    name
)
SELECT
    :tenant_id,
    hb.id,
    floor_data.floor_number,
    floor_data.name
FROM hospital_branches hb
CROSS JOIN (
    VALUES
        ('1', 'Primer piso'),
        ('2', 'Segundo piso')
) AS floor_data(floor_number, name)
WHERE hb.tenant_id = :tenant_id
  AND hb.code = 'BR-CENTRAL'
ON CONFLICT (tenant_id, branch_id, floor_number)
DO UPDATE SET
    name = EXCLUDED.name;

-- Salas
INSERT INTO rooms (
    tenant_id,
    branch_id,
    floor_id,
    department_id,
    room_number,
    room_type,
    status
)
SELECT
    :tenant_id,
    hb.id,
    fl.id,
    dp.id,
    room_data.room_number,
    room_data.room_type,
    room_data.status
FROM hospital_branches hb
CROSS JOIN (
    VALUES
        ('1', '101', 'emergencia', 'available', 'EMER'),
        ('1', '102', 'triaje', 'available', 'EMER'),
        ('2', '201', 'uci', 'available', 'UCI'),
        ('2', '202', 'hospitalizacion', 'available', 'HOSP')
) AS room_data(floor_number, room_number, room_type, status, department_code)
LEFT JOIN floors fl
    ON fl.tenant_id = :tenant_id
   AND fl.branch_id = hb.id
   AND fl.floor_number = room_data.floor_number
LEFT JOIN departments dp
    ON dp.tenant_id = :tenant_id
   AND dp.branch_id = hb.id
   AND dp.code = room_data.department_code
WHERE hb.tenant_id = :tenant_id
  AND hb.code = 'BR-CENTRAL'
ON CONFLICT (tenant_id, branch_id, room_number)
DO UPDATE SET
    floor_id = EXCLUDED.floor_id,
    department_id = EXCLUDED.department_id,
    room_type = EXCLUDED.room_type,
    status = EXCLUDED.status;

-- Camas
INSERT INTO beds (
    tenant_id,
    room_id,
    bed_type_id,
    bed_number,
    status
)
SELECT
    :tenant_id,
    rm.id,
    bt.id,
    bed_data.bed_number,
    bed_data.status
FROM rooms rm
JOIN hospital_branches hb
    ON hb.id = rm.branch_id
   AND hb.tenant_id = :tenant_id
CROSS JOIN (
    VALUES
        ('101', 'A', 'GEN', 'free'),
        ('101', 'B', 'GEN', 'occupied'),
        ('102', 'A', 'PED', 'maintenance'),
        ('201', 'A', 'UCI', 'occupied'),
        ('201', 'B', 'UCI', 'free'),
        ('202', 'A', 'GEN', 'free'),
        ('202', 'B', 'GEN', 'free')
) AS bed_data(room_number, bed_number, bed_type_code, status)
JOIN bed_types bt
    ON bt.tenant_id = :tenant_id
   AND bt.code = bed_data.bed_type_code
WHERE rm.tenant_id = :tenant_id
  AND rm.room_number = bed_data.room_number
  AND hb.code = 'BR-CENTRAL'
ON CONFLICT (tenant_id, room_id, bed_number)
DO UPDATE SET
    bed_type_id = EXCLUDED.bed_type_id,
    status = EXCLUDED.status;

-- Equipos
INSERT INTO equipment (
    tenant_id,
    branch_id,
    department_id,
    code,
    name,
    serial_number,
    purchase_date,
    status
)
SELECT
    :tenant_id,
    hb.id,
    dp.id,
    eq.code,
    eq.name,
    eq.serial_number,
    eq.purchase_date,
    eq.status
FROM hospital_branches hb
CROSS JOIN (
    VALUES
        ('EQ-MON-001', 'Monitor multiparametrico', 'SN-MON-001', DATE '2025-01-15', 'UCI', 'active'),
        ('EQ-VEN-001', 'Ventilador mecanico', 'SN-VEN-001', DATE '2025-02-10', 'UCI', 'active'),
        ('EQ-INF-001', 'Bomba de infusion', 'SN-INF-001', DATE '2025-03-05', 'HOSP', 'inactive')
) AS eq(code, name, serial_number, purchase_date, department_code, status)
LEFT JOIN departments dp
    ON dp.tenant_id = :tenant_id
   AND dp.branch_id = hb.id
   AND dp.code = eq.department_code
WHERE hb.tenant_id = :tenant_id
  AND hb.code = 'BR-CENTRAL'
ON CONFLICT (tenant_id, code)
DO UPDATE SET
    branch_id = EXCLUDED.branch_id,
    department_id = EXCLUDED.department_id,
    name = EXCLUDED.name,
    serial_number = EXCLUDED.serial_number,
    purchase_date = EXCLUDED.purchase_date,
    status = EXCLUDED.status;

-- Mantenimiento preventivo
INSERT INTO maintenance_schedule (
    tenant_id,
    equipment_id,
    maintenance_type,
    scheduled_date,
    performed_date,
    notes
)
SELECT
    :tenant_id,
    eq.id,
    ms_data.maintenance_type,
    ms_data.scheduled_date,
    ms_data.performed_date,
    ms_data.notes
FROM equipment eq
CROSS JOIN (
    VALUES
        ('EQ-MON-001', 'preventivo', DATE '2026-04-08', NULL::DATE, 'Calibracion trimestral'),
        ('EQ-VEN-001', 'preventivo', DATE '2026-04-15', NULL::DATE, 'Revision de filtros y alarmas'),
        ('EQ-INF-001', 'preventivo', DATE '2026-04-22', NULL::DATE, 'Chequeo funcional de bombeo')
) AS ms_data(equipment_code, maintenance_type, scheduled_date, performed_date, notes)
WHERE eq.tenant_id = :tenant_id
  AND eq.code = ms_data.equipment_code
  AND NOT EXISTS (
      SELECT 1
      FROM maintenance_schedule existing_ms
      WHERE existing_ms.tenant_id = :tenant_id
        AND existing_ms.equipment_id = eq.id
        AND existing_ms.maintenance_type = ms_data.maintenance_type
        AND existing_ms.scheduled_date = ms_data.scheduled_date
  );

-- OPERATIONAL_QUERIES

-- Disponibilidad de camas
SELECT
    hb.id AS branch_id,
    hb.name AS branch_name,
    fl.floor_number,
    fl.name AS floor_name,
    rm.room_number,
    rm.room_type,
    b.bed_number,
    bt.code AS bed_type_code,
    bt.name AS bed_type_name,
    b.status
FROM beds b
JOIN rooms rm
    ON rm.id = b.room_id
   AND rm.tenant_id = :tenant_id
JOIN hospital_branches hb
    ON hb.id = rm.branch_id
   AND hb.tenant_id = :tenant_id
LEFT JOIN floors fl
    ON fl.id = rm.floor_id
   AND fl.tenant_id = :tenant_id
LEFT JOIN bed_types bt
    ON bt.id = b.bed_type_id
   AND bt.tenant_id = :tenant_id
WHERE b.tenant_id = :tenant_id
  AND b.status = 'free'
  AND (:branch_id IS NULL OR hb.id = :branch_id)
ORDER BY hb.name, fl.floor_number, rm.room_number, b.bed_number;

-- Ocupacion por sede y piso
SELECT
    hb.id AS branch_id,
    hb.name AS branch_name,
    fl.id AS floor_id,
    fl.floor_number,
    fl.name AS floor_name,
    COUNT(b.id) AS total_beds,
    COUNT(*) FILTER (WHERE b.status = 'free') AS free_beds,
    COUNT(*) FILTER (WHERE b.status = 'occupied') AS occupied_beds,
    COUNT(*) FILTER (WHERE b.status = 'maintenance') AS maintenance_beds,
    ROUND(
        100.0 * COUNT(*) FILTER (WHERE b.status = 'occupied') / NULLIF(COUNT(b.id), 0),
        2
    ) AS occupancy_percent
FROM hospital_branches hb
JOIN floors fl
    ON fl.branch_id = hb.id
   AND fl.tenant_id = :tenant_id
JOIN rooms rm
    ON rm.branch_id = hb.id
   AND rm.floor_id = fl.id
   AND rm.tenant_id = :tenant_id
JOIN beds b
    ON b.room_id = rm.id
   AND b.tenant_id = :tenant_id
WHERE hb.tenant_id = :tenant_id
  AND (:branch_id IS NULL OR hb.id = :branch_id)
GROUP BY hb.id, hb.name, fl.id, fl.floor_number, fl.name
ORDER BY hb.name, fl.floor_number;

-- Equipos por estado
SELECT
    hb.id AS branch_id,
    hb.name AS branch_name,
    e.status,
    COUNT(*) AS total_equipment
FROM equipment e
JOIN hospital_branches hb
    ON hb.id = e.branch_id
   AND hb.tenant_id = :tenant_id
WHERE e.tenant_id = :tenant_id
  AND (:branch_id IS NULL OR hb.id = :branch_id)
GROUP BY hb.id, hb.name, e.status
ORDER BY hb.name, e.status;

-- Proximos mantenimientos
SELECT
    ms.id,
    hb.id AS branch_id,
    hb.name AS branch_name,
    e.code AS equipment_code,
    e.name AS equipment_name,
    ms.maintenance_type,
    ms.scheduled_date,
    ms.performed_date,
    ms.notes
FROM maintenance_schedule ms
JOIN equipment e
    ON e.id = ms.equipment_id
   AND e.tenant_id = :tenant_id
LEFT JOIN hospital_branches hb
    ON hb.id = e.branch_id
   AND hb.tenant_id = :tenant_id
WHERE ms.tenant_id = :tenant_id
  AND ms.performed_date IS NULL
  AND ms.scheduled_date BETWEEN CURRENT_DATE AND (CURRENT_DATE + 30)
  AND (:branch_id IS NULL OR hb.id = :branch_id)
ORDER BY ms.scheduled_date, hb.name, e.name;
