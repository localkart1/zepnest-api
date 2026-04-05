-- Add structured address fields to `addresses` and `customer_addresses`.
-- Run after backup: psql "$DATABASE_URL" -f scripts/alter_addresses_add_detail_columns.sql

ALTER TABLE addresses ADD COLUMN IF NOT EXISTS door_no VARCHAR(128);
ALTER TABLE addresses ADD COLUMN IF NOT EXISTS building_name VARCHAR(255);
ALTER TABLE addresses ADD COLUMN IF NOT EXISTS street VARCHAR(255);
ALTER TABLE addresses ADD COLUMN IF NOT EXISTS area VARCHAR(255);
ALTER TABLE addresses ADD COLUMN IF NOT EXISTS lat DOUBLE PRECISION;
ALTER TABLE addresses ADD COLUMN IF NOT EXISTS long DOUBLE PRECISION;
ALTER TABLE addresses ADD COLUMN IF NOT EXISTS phone_no VARCHAR(32);
ALTER TABLE addresses ADD COLUMN IF NOT EXISTS name VARCHAR(255);

ALTER TABLE customer_addresses ADD COLUMN IF NOT EXISTS door_no VARCHAR(128);
ALTER TABLE customer_addresses ADD COLUMN IF NOT EXISTS building_name VARCHAR(255);
ALTER TABLE customer_addresses ADD COLUMN IF NOT EXISTS street VARCHAR(255);
ALTER TABLE customer_addresses ADD COLUMN IF NOT EXISTS area VARCHAR(255);
ALTER TABLE customer_addresses ADD COLUMN IF NOT EXISTS lat DOUBLE PRECISION;
ALTER TABLE customer_addresses ADD COLUMN IF NOT EXISTS long DOUBLE PRECISION;
ALTER TABLE customer_addresses ADD COLUMN IF NOT EXISTS phone_no VARCHAR(32);
ALTER TABLE customer_addresses ADD COLUMN IF NOT EXISTS name VARCHAR(255);
