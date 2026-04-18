-- LOAD_QUERIES
-- PostgreSQL loader for patient master data.
-- Placeholder order:
-- $1  tenant_id
-- $2  branch_id
-- $3  patient_code
-- $4  first_name
-- $5  last_name
-- $6  date_of_birth
-- $7  sex
-- $8  blood_type_code
-- $9  ethnic_group_code
-- $10 national_id
-- $11 phone
-- $12 email
-- $13 address
-- $14 city_id
-- $15 status
-- $16 contacts_jsonb
-- $17 documents_jsonb
-- $18 insurance_jsonb
-- $19 allergies_jsonb
-- $20 risk_factors_jsonb

-- Seed blood types for the tenant
INSERT INTO blood_types (tenant_id, code, description)
VALUES
    ($1::uuid, 'O+', 'Grupo O positivo'),
    ($1::uuid, 'O-', 'Grupo O negativo'),
    ($1::uuid, 'A+', 'Grupo A positivo'),
    ($1::uuid, 'A-', 'Grupo A negativo'),
    ($1::uuid, 'B+', 'Grupo B positivo'),
    ($1::uuid, 'B-', 'Grupo B negativo'),
    ($1::uuid, 'AB+', 'Grupo AB positivo'),
    ($1::uuid, 'AB-', 'Grupo AB negativo')
ON CONFLICT (tenant_id, code)
DO UPDATE SET
    description = EXCLUDED.description;

-- Seed ethnic groups for the tenant
INSERT INTO ethnic_groups (tenant_id, code, name)
VALUES
    ($1::uuid, 'MESTIZO', 'Mestizo'),
    ($1::uuid, 'INDIGENA', 'Indigena'),
    ($1::uuid, 'AFRODESCENDIENTE', 'Afrodescendiente'),
    ($1::uuid, 'BLANCO', 'Blanco'),
    ($1::uuid, 'ASIATICO', 'Asiatico'),
    ($1::uuid, 'OTRO', 'Otro')
ON CONFLICT (tenant_id, code)
DO UPDATE SET
    name = EXCLUDED.name;

-- Full patient master insert template
WITH params AS (
    SELECT
        $1::uuid AS tenant_id,
        $2::uuid AS branch_id,
        NULLIF($3::text, '') AS patient_code,
        $4::text AS first_name,
        $5::text AS last_name,
        $6::date AS date_of_birth,
        NULLIF($7::text, '') AS sex,
        NULLIF($8::text, '') AS blood_type_code,
        NULLIF($9::text, '') AS ethnic_group_code,
        NULLIF($10::text, '') AS national_id,
        NULLIF($11::text, '') AS phone,
        NULLIF($12::text, '') AS email,
        NULLIF($13::text, '') AS address,
        $14::uuid AS city_id,
        COALESCE(NULLIF($15::text, ''), 'active') AS status
),
new_patient AS (
    INSERT INTO patients (
        tenant_id,
        branch_id,
        patient_code,
        first_name,
        last_name,
        date_of_birth,
        sex,
        blood_type_id,
        ethnic_group_id,
        national_id,
        phone,
        email,
        address,
        city_id,
        status
    )
    SELECT
        p.tenant_id,
        p.branch_id,
        p.patient_code,
        p.first_name,
        p.last_name,
        p.date_of_birth,
        p.sex,
        bt.id,
        eg.id,
        p.national_id,
        p.phone,
        p.email,
        p.address,
        p.city_id,
        p.status
    FROM params p
    LEFT JOIN blood_types bt
        ON bt.tenant_id = p.tenant_id
       AND bt.code = p.blood_type_code
    LEFT JOIN ethnic_groups eg
        ON eg.tenant_id = p.tenant_id
       AND eg.code = p.ethnic_group_code
    RETURNING id, tenant_id
),
inserted_contacts AS (
    INSERT INTO patient_contacts (
        tenant_id,
        patient_id,
        full_name,
        relationship,
        phone,
        email,
        is_primary
    )
    SELECT
        np.tenant_id,
        np.id,
        c.full_name,
        c.relationship,
        c.phone,
        c.email,
        COALESCE(c.is_primary, FALSE)
    FROM new_patient np
    CROSS JOIN LATERAL jsonb_to_recordset(COALESCE($16::jsonb, '[]'::jsonb))
        AS c(
            full_name text,
            relationship text,
            phone text,
            email text,
            is_primary boolean
        )
    RETURNING id
),
inserted_documents AS (
    INSERT INTO patient_documents (
        tenant_id,
        patient_id,
        document_type,
        document_number,
        file_url,
        issued_at,
        expires_at
    )
    SELECT
        np.tenant_id,
        np.id,
        d.document_type,
        d.document_number,
        d.file_url,
        d.issued_at,
        d.expires_at
    FROM new_patient np
    CROSS JOIN LATERAL jsonb_to_recordset(COALESCE($17::jsonb, '[]'::jsonb))
        AS d(
            document_type text,
            document_number text,
            file_url text,
            issued_at date,
            expires_at date
        )
    RETURNING id
),
inserted_insurance AS (
    INSERT INTO patient_insurance (
        tenant_id,
        patient_id,
        provider_name,
        policy_number,
        plan_name,
        valid_from,
        valid_to,
        is_primary
    )
    SELECT
        np.tenant_id,
        np.id,
        i.provider_name,
        i.policy_number,
        i.plan_name,
        i.valid_from,
        i.valid_to,
        COALESCE(i.is_primary, TRUE)
    FROM new_patient np
    CROSS JOIN LATERAL jsonb_to_recordset(COALESCE($18::jsonb, '[]'::jsonb))
        AS i(
            provider_name text,
            policy_number text,
            plan_name text,
            valid_from date,
            valid_to date,
            is_primary boolean
        )
    RETURNING id
),
inserted_allergies AS (
    INSERT INTO patient_allergies (
        tenant_id,
        patient_id,
        allergen,
        severity,
        reaction,
        noted_at
    )
    SELECT
        np.tenant_id,
        np.id,
        a.allergen,
        a.severity,
        a.reaction,
        a.noted_at
    FROM new_patient np
    CROSS JOIN LATERAL jsonb_to_recordset(COALESCE($19::jsonb, '[]'::jsonb))
        AS a(
            allergen text,
            severity text,
            reaction text,
            noted_at timestamptz
        )
    RETURNING id
),
inserted_risk_factors AS (
    INSERT INTO patient_risk_factors (
        tenant_id,
        patient_id,
        factor_type,
        value,
        notes,
        recorded_at
    )
    SELECT
        np.tenant_id,
        np.id,
        r.factor_type,
        r.value,
        r.notes,
        r.recorded_at
    FROM new_patient np
    CROSS JOIN LATERAL jsonb_to_recordset(COALESCE($20::jsonb, '[]'::jsonb))
        AS r(
            factor_type text,
            value text,
            notes text,
            recorded_at timestamptz
        )
    RETURNING id
)
SELECT
    np.id AS patient_id,
    (SELECT COUNT(*) FROM inserted_contacts) AS contacts_inserted,
    (SELECT COUNT(*) FROM inserted_documents) AS documents_inserted,
    (SELECT COUNT(*) FROM inserted_insurance) AS insurance_inserted,
    (SELECT COUNT(*) FROM inserted_allergies) AS allergies_inserted,
    (SELECT COUNT(*) FROM inserted_risk_factors) AS risk_factors_inserted
FROM new_patient np;

-- OPERATIONAL_QUERIES

-- Search patients by document or name
WITH search_term AS (
    SELECT NULLIF($2::text, '') AS query_text
)
SELECT
    p.id,
    p.tenant_id,
    p.patient_code,
    p.national_id,
    p.first_name,
    p.last_name,
    p.date_of_birth,
    p.sex,
    p.phone,
    p.email,
    p.status,
    bt.code AS blood_type_code,
    bt.description AS blood_type_description,
    eg.code AS ethnic_group_code,
    eg.name AS ethnic_group_name,
    doc.document_type AS primary_document_type,
    doc.document_number AS primary_document_number
FROM patients p
LEFT JOIN blood_types bt
    ON bt.id = p.blood_type_id
LEFT JOIN ethnic_groups eg
    ON eg.id = p.ethnic_group_id
LEFT JOIN LATERAL (
    SELECT
        pd.document_type,
        pd.document_number
    FROM patient_documents pd
    WHERE pd.tenant_id = p.tenant_id
      AND pd.patient_id = p.id
    ORDER BY pd.created_at DESC
    LIMIT 1
) doc ON TRUE
JOIN search_term s ON TRUE
WHERE p.tenant_id = $1::uuid
  AND s.query_text IS NOT NULL
  AND (
      p.national_id = s.query_text
      OR p.patient_code = s.query_text
      OR p.first_name ILIKE '%' || s.query_text || '%'
      OR p.last_name ILIKE '%' || s.query_text || '%'
      OR concat_ws(' ', p.first_name, p.last_name) ILIKE '%' || s.query_text || '%'
      OR EXISTS (
          SELECT 1
          FROM patient_documents pdx
          WHERE pdx.tenant_id = p.tenant_id
            AND pdx.patient_id = p.id
            AND (
                pdx.document_number = s.query_text
                OR pdx.document_number ILIKE '%' || s.query_text || '%'
                OR pdx.document_type ILIKE '%' || s.query_text || '%'
            )
      )
  )
ORDER BY p.last_name, p.first_name, p.patient_code
LIMIT COALESCE($3::int, 50);

-- Clinical profile summary
SELECT
    p.id,
    p.tenant_id,
    p.patient_code,
    p.national_id,
    p.first_name,
    p.last_name,
    p.date_of_birth,
    date_part('year', age(current_date, p.date_of_birth))::int AS age_years,
    p.sex,
    p.phone,
    p.email,
    p.address,
    p.status,
    bt.code AS blood_type_code,
    bt.description AS blood_type_description,
    eg.code AS ethnic_group_code,
    eg.name AS ethnic_group_name,
    COALESCE(ct.contacts, '[]'::jsonb) AS contacts,
    COALESCE(dc.documents, '[]'::jsonb) AS documents,
    COALESCE(ins.insurance, '[]'::jsonb) AS insurance,
    COALESCE(alg.allergies, '[]'::jsonb) AS allergies,
    COALESCE(alg.critical_allergy_count, 0) AS critical_allergy_count,
    COALESCE(rf.risk_factors, '[]'::jsonb) AS risk_factors
FROM patients p
LEFT JOIN blood_types bt
    ON bt.id = p.blood_type_id
LEFT JOIN ethnic_groups eg
    ON eg.id = p.ethnic_group_id
LEFT JOIN LATERAL (
    SELECT jsonb_agg(
        jsonb_build_object(
            'id', pc.id,
            'full_name', pc.full_name,
            'relationship', pc.relationship,
            'phone', pc.phone,
            'email', pc.email,
            'is_primary', pc.is_primary,
            'created_at', pc.created_at
        )
        ORDER BY pc.is_primary DESC, pc.created_at DESC
    ) AS contacts
    FROM patient_contacts pc
    WHERE pc.tenant_id = p.tenant_id
      AND pc.patient_id = p.id
) ct ON TRUE
LEFT JOIN LATERAL (
    SELECT jsonb_agg(
        jsonb_build_object(
            'id', pd.id,
            'document_type', pd.document_type,
            'document_number', pd.document_number,
            'file_url', pd.file_url,
            'issued_at', pd.issued_at,
            'expires_at', pd.expires_at,
            'created_at', pd.created_at
        )
        ORDER BY pd.created_at DESC
    ) AS documents
    FROM patient_documents pd
    WHERE pd.tenant_id = p.tenant_id
      AND pd.patient_id = p.id
) dc ON TRUE
LEFT JOIN LATERAL (
    SELECT jsonb_agg(
        jsonb_build_object(
            'id', pi.id,
            'provider_name', pi.provider_name,
            'policy_number', pi.policy_number,
            'plan_name', pi.plan_name,
            'valid_from', pi.valid_from,
            'valid_to', pi.valid_to,
            'is_primary', pi.is_primary,
            'created_at', pi.created_at
        )
        ORDER BY pi.is_primary DESC, pi.created_at DESC
    ) AS insurance
    FROM patient_insurance pi
    WHERE pi.tenant_id = p.tenant_id
      AND pi.patient_id = p.id
) ins ON TRUE
LEFT JOIN LATERAL (
    SELECT
        jsonb_agg(
            jsonb_build_object(
                'id', pa.id,
                'allergen', pa.allergen,
                'severity', pa.severity,
                'reaction', pa.reaction,
                'noted_at', pa.noted_at,
                'created_at', pa.created_at
            )
            ORDER BY pa.created_at DESC
        ) AS allergies,
        COUNT(*) FILTER (
            WHERE lower(COALESCE(pa.severity, '')) IN ('critical', 'grave', 'severe', 'high')
        ) AS critical_allergy_count
    FROM patient_allergies pa
    WHERE pa.tenant_id = p.tenant_id
      AND pa.patient_id = p.id
) alg ON TRUE
LEFT JOIN LATERAL (
    SELECT jsonb_agg(
        jsonb_build_object(
            'id', prf.id,
            'factor_type', prf.factor_type,
            'value', prf.value,
            'notes', prf.notes,
            'recorded_at', prf.recorded_at,
            'created_at', prf.created_at
        )
        ORDER BY prf.recorded_at DESC NULLS LAST, prf.created_at DESC
    ) AS risk_factors
    FROM patient_risk_factors prf
    WHERE prf.tenant_id = p.tenant_id
      AND prf.patient_id = p.id
) rf ON TRUE
WHERE p.tenant_id = $1::uuid
  AND p.id = $2::uuid;

-- Critical allergies
SELECT
    p.id AS patient_id,
    p.patient_code,
    p.national_id,
    p.first_name,
    p.last_name,
    pa.id AS allergy_id,
    pa.allergen,
    pa.severity,
    pa.reaction,
    pa.noted_at,
    pa.created_at
FROM patient_allergies pa
JOIN patients p
    ON p.id = pa.patient_id
   AND p.tenant_id = pa.tenant_id
WHERE pa.tenant_id = $1::uuid
  AND lower(COALESCE(pa.severity, '')) IN ('critical', 'grave', 'severe', 'high')
ORDER BY pa.severity DESC, pa.created_at DESC, p.last_name, p.first_name;

-- Patients by insurance
SELECT
    p.id AS patient_id,
    p.patient_code,
    p.national_id,
    p.first_name,
    p.last_name,
    p.phone,
    p.email,
    pi.id AS insurance_id,
    pi.provider_name,
    pi.policy_number,
    pi.plan_name,
    pi.valid_from,
    pi.valid_to,
    pi.is_primary,
    pi.created_at
FROM patient_insurance pi
JOIN patients p
    ON p.id = pi.patient_id
   AND p.tenant_id = pi.tenant_id
WHERE pi.tenant_id = $1::uuid
  AND (
      $2::text IS NULL
      OR pi.provider_name ILIKE '%' || $2::text || '%'
      OR pi.plan_name ILIKE '%' || $2::text || '%'
      OR pi.policy_number ILIKE '%' || $2::text || '%'
  )
ORDER BY pi.provider_name, pi.is_primary DESC, p.last_name, p.first_name
LIMIT COALESCE($3::int, 100);
