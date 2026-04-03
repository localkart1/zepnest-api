-- Maps which services are offered in which geographic areas (``service_areas``).
-- Used by ``GET /mobile/home`` to filter categories/services by the user's PIN / zip.
--
-- Example: psql "$DATABASE_URL" -f scripts/create_service_area_services.sql

CREATE TABLE IF NOT EXISTS service_area_services (
    area_id INTEGER NOT NULL REFERENCES service_areas (area_id) ON DELETE CASCADE,
    service_id INTEGER NOT NULL REFERENCES services (service_id) ON DELETE CASCADE,
    PRIMARY KEY (area_id, service_id)
);

CREATE INDEX IF NOT EXISTS idx_service_area_services_service_id ON service_area_services (service_id);
