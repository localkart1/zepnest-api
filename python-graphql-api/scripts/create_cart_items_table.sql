-- Per-customer shopping cart lines (mobile). Run once on PostgreSQL.
-- psql "$DATABASE_URL" -f scripts/create_cart_items_table.sql
--
-- If `cart_items` already exists but is missing columns (e.g. notes, voice_url), run:
--   psql "$DATABASE_URL" -f scripts/alter_cart_items_add_detail_columns.sql

CREATE TABLE IF NOT EXISTS cart_items (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users (user_id) ON DELETE CASCADE,
    service_id INTEGER NOT NULL REFERENCES services (service_id) ON DELETE CASCADE,
    quantity INTEGER NOT NULL DEFAULT 1 CHECK (quantity > 0),
    unit_price NUMERIC(12, 2) NOT NULL DEFAULT 0,
    total_price NUMERIC(12, 2) NOT NULL DEFAULT 0,
    notes TEXT,
    voice_url TEXT,
    video_url TEXT,
    image_url TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_cart_items_user_service UNIQUE (user_id, service_id)
);

CREATE INDEX IF NOT EXISTS idx_cart_items_user_id ON cart_items (user_id);
