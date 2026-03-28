-- Normalized catalog: categories, sub_categories, price_mappings + services.category_id
-- Run once against Postgres if AUTO_CREATE_TABLES is false.
-- Example: psql "$DATABASE_URL" -f scripts/create_categories_schema.sql

-- --- Core tables (match api/models/service_catalog.py) ---

CREATE TABLE IF NOT EXISTS categories (
    id SERIAL PRIMARY KEY,
    name VARCHAR(120) NOT NULL,
    description TEXT,
    icon VARCHAR(255),
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_categories_name UNIQUE (name)
);

CREATE TABLE IF NOT EXISTS sub_categories (
    id SERIAL PRIMARY KEY,
    category_id INTEGER NOT NULL REFERENCES categories (id) ON DELETE CASCADE,
    name VARCHAR(120) NOT NULL,
    description TEXT,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
    CONSTRAINT unique_category_subcategory UNIQUE (category_id, name)
);

CREATE INDEX IF NOT EXISTS ix_sub_categories_category_id ON sub_categories (category_id);

CREATE TABLE IF NOT EXISTS price_mappings (
    id SERIAL PRIMARY KEY,
    category_id INTEGER NOT NULL REFERENCES categories (id) ON DELETE CASCADE,
    sub_category_id INTEGER REFERENCES sub_categories (id) ON DELETE SET NULL,
    service_name VARCHAR(255) NOT NULL,
    service_type VARCHAR(50) NOT NULL,
    base_price DOUBLE PRECISION NOT NULL,
    gst_percentage DOUBLE PRECISION DEFAULT 18.0,
    total_price DOUBLE PRECISION NOT NULL,
    unit VARCHAR(50) DEFAULT 'per service',
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_price_mappings_category_id ON price_mappings (category_id);

-- --- Link services to categories (nullable for gradual migration) ---

ALTER TABLE services ADD COLUMN IF NOT EXISTS category_id INTEGER REFERENCES categories (id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS ix_services_category_id ON services (category_id);

-- --- Seed categories from existing service strings + default ---

INSERT INTO categories (name, description, is_active, created_at, updated_at)
VALUES ('General', '', TRUE, NOW(), NOW())
ON CONFLICT (name) DO NOTHING;

INSERT INTO categories (name, description, is_active, created_at, updated_at)
SELECT DISTINCT TRIM(category), '', TRUE, NOW(), NOW()
FROM services
WHERE category IS NOT NULL AND TRIM(category) <> ''
ON CONFLICT (name) DO NOTHING;

UPDATE services s
SET category_id = c.id
FROM categories c
WHERE s.category_id IS NULL
  AND s.category IS NOT NULL
  AND TRIM(s.category) = c.name;

-- --- Sample subcategories (idempotent; skips if category name is absent) ---

INSERT INTO sub_categories (category_id, name, description, is_active, created_at, updated_at)
SELECT c.id, v.sub_name, v.sub_desc, TRUE, NOW(), NOW()
FROM categories c
INNER JOIN (
    VALUES
        ('General', 'Installation', 'New unit installation'),
        ('General', 'Repair', 'Breakdown and on-site repair'),
        ('General', 'Maintenance', 'Periodic servicing and tune-up')
) AS v (cat_name, sub_name, sub_desc) ON TRIM(c.name) = TRIM(v.cat_name)
ON CONFLICT (category_id, name) DO NOTHING;

INSERT INTO sub_categories (category_id, name, description, is_active, created_at, updated_at)
SELECT c.id, v.sub_name, v.sub_desc, TRUE, NOW(), NOW()
FROM categories c
INNER JOIN (
    VALUES
        ('AC', 'Split AC', 'Split and ductable systems'),
        ('AC', 'Window AC', 'Window-type units'),
        ('AC', 'Gas refill', 'Gas top-up and leak check')
) AS v (cat_name, sub_name, sub_desc) ON TRIM(c.name) = TRIM(v.cat_name)
ON CONFLICT (category_id, name) DO NOTHING;

INSERT INTO sub_categories (category_id, name, description, is_active, created_at, updated_at)
SELECT c.id, v.sub_name, v.sub_desc, TRUE, NOW(), NOW()
FROM categories c
INNER JOIN (
    VALUES
        ('RO', 'RO service', 'Full RO health check'),
        ('RO', 'Filter replacement', 'Sediment / carbon / membrane'),
        ('Refrigerator', 'Gas charging', 'Cooling gas and leak test'),
        ('Refrigerator', 'General service', 'Cleaning and inspection')
) AS v (cat_name, sub_name, sub_desc) ON TRIM(c.name) = TRIM(v.cat_name)
ON CONFLICT (category_id, name) DO NOTHING;
