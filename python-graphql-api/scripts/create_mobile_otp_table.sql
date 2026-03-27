-- Run once against your Postgres DB if AUTO_CREATE_TABLES is false.
-- Example: psql "$DATABASE_URL" -f scripts/create_mobile_otp_table.sql

CREATE TABLE IF NOT EXISTS mobile_otp_sessions (
    id SERIAL PRIMARY KEY,
    phone VARCHAR(32) NOT NULL,
    otp_hash VARCHAR(128) NOT NULL,
    expires_at TIMESTAMP NOT NULL,
    consumed BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_mobile_otp_sessions_phone ON mobile_otp_sessions (phone);
