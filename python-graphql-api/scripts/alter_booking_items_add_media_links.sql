-- Add media URL columns to booking_items.
-- Safe to run multiple times.

ALTER TABLE booking_items ADD COLUMN IF NOT EXISTS voice_url TEXT;
ALTER TABLE booking_items ADD COLUMN IF NOT EXISTS video_url TEXT;
ALTER TABLE booking_items ADD COLUMN IF NOT EXISTS image_url TEXT;

