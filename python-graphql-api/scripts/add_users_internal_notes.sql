-- Admin portal: persist customer internal notes on users.
-- psql "$DATABASE_URL" -f scripts/add_users_internal_notes.sql

ALTER TABLE users ADD COLUMN IF NOT EXISTS internal_notes TEXT;
