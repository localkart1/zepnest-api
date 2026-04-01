-- Reviews table for customer feedback.

CREATE TABLE IF NOT EXISTS reviews (
    review_id SERIAL PRIMARY KEY,
    booking_id INTEGER NULL REFERENCES bookings(booking_id) ON DELETE SET NULL,
    customer_id INTEGER NULL REFERENCES users(user_id) ON DELETE SET NULL,
    technician_id INTEGER NULL REFERENCES technician_profiles(technician_id) ON DELETE SET NULL,
    rating INTEGER NOT NULL CHECK (rating >= 1 AND rating <= 5),
    title VARCHAR(255),
    review_text TEXT,
    is_active BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_reviews_booking_id ON reviews (booking_id);
CREATE INDEX IF NOT EXISTS idx_reviews_customer_id ON reviews (customer_id);
CREATE INDEX IF NOT EXISTS idx_reviews_technician_id ON reviews (technician_id);
CREATE INDEX IF NOT EXISTS idx_reviews_is_active ON reviews (is_active);

