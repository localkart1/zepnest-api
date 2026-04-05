-- Add per-line notes and media URL columns to an existing `cart_items` table.
-- Use this when CREATE TABLE already ran without these columns (IF NOT EXISTS skipped new fields).
--
--   psql "$DATABASE_URL" -f scripts/alter_cart_items_add_detail_columns.sql
--
-- Optional: if your table also predates pricing columns, uncomment the two ALTERs at the bottom.

ALTER TABLE cart_items ADD COLUMN IF NOT EXISTS notes TEXT;
ALTER TABLE cart_items ADD COLUMN IF NOT EXISTS voice_url TEXT;
ALTER TABLE cart_items ADD COLUMN IF NOT EXISTS video_url TEXT;
ALTER TABLE cart_items ADD COLUMN IF NOT EXISTS image_url TEXT;

-- Uncomment only if `unit_price` / `total_price` are missing (check: \d cart_items in psql).
-- ALTER TABLE cart_items ADD COLUMN IF NOT EXISTS unit_price NUMERIC(12, 2) NOT NULL DEFAULT 0;
-- ALTER TABLE cart_items ADD COLUMN IF NOT EXISTS total_price NUMERIC(12, 2) NOT NULL DEFAULT 0;
