-- Create time_slot_master and seed 30-minute slots.
-- Range: 07:30 to 18:00 (inclusive end via last slot 17:30 - 18:00)

CREATE TABLE IF NOT EXISTS time_slot_master (
    id SERIAL PRIMARY KEY,
    time_slot VARCHAR(32) NOT NULL UNIQUE,
    active CHAR(1) NOT NULL DEFAULT 'Y',
    CONSTRAINT chk_time_slot_master_active CHECK (active IN ('Y', 'N'))
);

INSERT INTO time_slot_master (time_slot, active)
SELECT
    to_char(ts, 'HH24:MI') || ' - ' || to_char(ts + interval '30 minutes', 'HH24:MI') AS time_slot,
    'Y' AS active
FROM generate_series(
    timestamp '2000-01-01 07:30:00',
    timestamp '2000-01-01 17:30:00',
    interval '30 minutes'
) AS ts
ON CONFLICT (time_slot) DO NOTHING;

