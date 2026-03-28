-- List labels for PostgreSQL enum ``booking_status_enum`` (adjust typname if yours differs).
-- psql "$DATABASE_URL" -f scripts/pg_list_booking_status_enum.sql

SELECT e.enumlabel AS booking_status
FROM pg_enum e
JOIN pg_type t ON e.enumtypid = t.oid
WHERE t.typname = 'booking_status_enum'
ORDER BY e.enumsortorder;
