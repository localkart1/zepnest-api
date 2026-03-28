-- Sample rows for ``bookings`` (GraphQL ``serviceBookings`` / REST orders).
-- Idempotent: skips inserts if demo booking numbers already exist.
--
-- Prerequisites: ``users`` table. Optional: ``services`` (for mobile-json sample).
-- Run:  source .env  # or export DATABASE_URL=postgresql://...
--       psql "$DATABASE_URL" -f scripts/seed_sample_bookings.sql

-- Demo customer (only if this email is not already present)
INSERT INTO users (email, password_hash, phone, first_name, last_name, user_type, loyalty_points, is_active, created_at, updated_at)
SELECT 'seed-bookings-demo@local.test', '', '+10000000001', 'Seed', 'Customer', 'customer', 100, true, NOW(), NOW()
WHERE NOT EXISTS (SELECT 1 FROM users WHERE email = 'seed-bookings-demo@local.test');

-- 1) GraphQL-style note (matches createServiceBooking text pattern)
INSERT INTO bookings (
    booking_number, customer_id, technician_id, service_address, status,
    subtotal, discount_amount, loyalty_points_used, loyalty_discount,
    total_amount, loyalty_points_earned, is_subscription_booking,
    customer_notes, created_at, updated_at
)
SELECT
    'DEMO-ORD-001',
    COALESCE(
        (SELECT user_id FROM users WHERE email = 'seed-bookings-demo@local.test' LIMIT 1),
        (SELECT user_id FROM users WHERE user_type = 'customer' ORDER BY user_id LIMIT 1)
    ),
    NULL,
    '123 Demo Street, Sample City',
    'pending',
    1500.0, 0.0, 0, 0.0,
    1500.0, 50, false,
    '[graphql service booking] service_type=repair asset_id=1 scheduled=2026-04-01 slot=morning',
    NOW() - INTERVAL '2 days',
    NOW() - INTERVAL '2 days'
WHERE NOT EXISTS (SELECT 1 FROM bookings WHERE booking_number = 'DEMO-ORD-001');

-- 2) Assigned / in progress style
INSERT INTO bookings (
    booking_number, customer_id, technician_id, service_address, status,
    subtotal, discount_amount, loyalty_points_used, loyalty_discount,
    total_amount, loyalty_points_earned, is_subscription_booking,
    customer_notes, created_at, updated_at
)
SELECT
    'DEMO-ORD-002',
    COALESCE(
        (SELECT user_id FROM users WHERE email = 'seed-bookings-demo@local.test' LIMIT 1),
        (SELECT user_id FROM users WHERE user_type = 'customer' ORDER BY user_id LIMIT 1)
    ),
    (SELECT technician_id FROM technician_profiles ORDER BY technician_id LIMIT 1),  -- NULL if no technicians
    '45 MG Road, Demo Town',
    'assigned',
    800.0, 50.0, 0, 0.0,
    750.0, 20, false,
    'Customer prefers weekend slot',
    NOW() - INTERVAL '1 day',
    NOW() - INTERVAL '1 day'
WHERE NOT EXISTS (SELECT 1 FROM bookings WHERE booking_number = 'DEMO-ORD-002');

-- 3) Escalated sample (notes similar to REST escalate_order)
INSERT INTO bookings (
    booking_number, customer_id, technician_id, service_address, status,
    subtotal, discount_amount, loyalty_points_used, loyalty_discount,
    total_amount, loyalty_points_earned, is_subscription_booking,
    customer_notes, created_at, updated_at
)
SELECT
    'DEMO-ORD-003',
    COALESCE(
        (SELECT user_id FROM users WHERE email = 'seed-bookings-demo@local.test' LIMIT 1),
        (SELECT user_id FROM users WHERE user_type = 'customer' ORDER BY user_id LIMIT 1)
    ),
    NULL,
    'Plot 7, Industrial Area',
    'escalated',
    2200.0, 0.0, 100, 0.0,
    2100.0, 0, false,
    'Follow-up needed | ESCALATION: Parts delay',
    NOW() - INTERVAL '5 days',
    NOW() - INTERVAL '1 hour'
WHERE NOT EXISTS (SELECT 1 FROM bookings WHERE booking_number = 'DEMO-ORD-003');

-- 4) Mobile app JSON notes (see api/mobile/routes.py MOBILE_JSON_PREFIX); requires at least one active service
INSERT INTO bookings (
    booking_number, customer_id, technician_id, service_address, status,
    subtotal, discount_amount, loyalty_points_used, loyalty_discount,
    total_amount, loyalty_points_earned, is_subscription_booking,
    customer_notes, created_at, updated_at
)
SELECT
    'DEMO-ORD-004',
    COALESCE(
        (SELECT user_id FROM users WHERE email = 'seed-bookings-demo@local.test' LIMIT 1),
        (SELECT user_id FROM users WHERE user_type = 'customer' ORDER BY user_id LIMIT 1)
    ),
    NULL,
    '88 Mobile Test Nagar',
    'pending',
    svc.tot,
    0.0, 0, 0.0,
    svc.tot,
    0, false,
    '[mobile-json]' || svc.payload::text,
    NOW() - INTERVAL '3 hours',
    NOW() - INTERVAL '3 hours'
FROM (
    SELECT
        COALESCE(SUM(x.base_price::double precision), 500.0) AS tot,
        json_build_object(
            'serviceIds', ARRAY_AGG(x.service_id ORDER BY x.service_id),
            'description', 'Seeded mobile-style booking',
            'voiceNoteUrl', '',
            'videoUrl', '',
            'customerNotes', 'Sample data from seed_sample_bookings.sql'
        ) AS payload
    FROM (
        SELECT service_id, base_price
        FROM services
        WHERE is_active = true
        ORDER BY service_id
        LIMIT 3
    ) x
) svc
WHERE NOT EXISTS (SELECT 1 FROM bookings WHERE booking_number = 'DEMO-ORD-004')
  AND EXISTS (SELECT 1 FROM services WHERE is_active = true);
