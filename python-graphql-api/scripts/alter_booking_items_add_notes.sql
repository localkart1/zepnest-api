-- Add notes column to booking_items.
-- Safe to run multiple times.

ALTER TABLE booking_items ADD COLUMN IF NOT EXISTS notes TEXT;

