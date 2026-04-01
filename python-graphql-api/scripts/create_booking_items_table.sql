-- Booking line items (1 booking -> many items)
-- Run once in PostgreSQL.

CREATE TABLE IF NOT EXISTS booking_items (
    id BIGSERIAL PRIMARY KEY,
    booking_id INTEGER NOT NULL,
    service_id INTEGER NOT NULL,
    quantity INTEGER NOT NULL DEFAULT 1,
    unit_price NUMERIC(12,2) NOT NULL DEFAULT 0,
    total_price NUMERIC(12,2) NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT fk_booking_items_booking
        FOREIGN KEY (booking_id) REFERENCES bookings (booking_id)
        ON DELETE CASCADE,
    CONSTRAINT fk_booking_items_service
        FOREIGN KEY (service_id) REFERENCES services (service_id)
        ON DELETE RESTRICT
);

CREATE INDEX IF NOT EXISTS idx_booking_items_booking_id ON booking_items (booking_id);
CREATE INDEX IF NOT EXISTS idx_booking_items_service_id ON booking_items (service_id);

