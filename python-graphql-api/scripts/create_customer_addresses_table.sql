-- Run once if AUTO_CREATE_TABLES is false.
-- psql "$DATABASE_URL" -f scripts/create_customer_addresses_table.sql

CREATE TABLE IF NOT EXISTS customer_addresses (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL,
    label VARCHAR(64),
    line1 VARCHAR(255) NOT NULL,
    line2 VARCHAR(255),
    city VARCHAR(100),
    state VARCHAR(100),
    zip_code VARCHAR(20),
    country VARCHAR(80) DEFAULT 'India',
    is_default BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_customer_addresses_user_id ON customer_addresses (user_id);
