-- Common addresses table linked to users (all user types).
-- Run once in PostgreSQL.

CREATE TABLE IF NOT EXISTS addresses (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL,
    label VARCHAR(64),
    line1 VARCHAR(255) NOT NULL,
    line2 VARCHAR(255),
    city VARCHAR(100),
    state VARCHAR(100),
    zip_code VARCHAR(20),
    country VARCHAR(80) DEFAULT 'India',
    address_type VARCHAR(32) DEFAULT 'home',
    is_default BOOLEAN NOT NULL DEFAULT false,
    door_no VARCHAR(128),
    building_name VARCHAR(255),
    street VARCHAR(255),
    area VARCHAR(255),
    lat DOUBLE PRECISION,
    long DOUBLE PRECISION,
    phone_no VARCHAR(32),
    name VARCHAR(255),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT fk_addresses_user FOREIGN KEY (user_id) REFERENCES users (user_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_addresses_user_id ON addresses (user_id);
CREATE INDEX IF NOT EXISTS idx_addresses_user_default ON addresses (user_id, is_default);

