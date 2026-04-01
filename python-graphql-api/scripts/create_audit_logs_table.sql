-- Audit log table for API-driven DB mutations.
-- Run once on your target PostgreSQL database.

CREATE TABLE IF NOT EXISTS audit_logs (
    id BIGSERIAL PRIMARY KEY,
    occurred_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    actor_user_id INTEGER NULL,
    actor_type VARCHAR(32) NULL,
    action VARCHAR(16) NOT NULL,
    table_name VARCHAR(128) NULL,
    http_method VARCHAR(10) NULL,
    request_path VARCHAR(255) NULL,
    endpoint VARCHAR(128) NULL,
    remote_addr VARCHAR(64) NULL,
    user_agent VARCHAR(255) NULL,
    sql_text TEXT NOT NULL,
    sql_params TEXT NULL,
    request_query TEXT NULL,
    request_body TEXT NULL
);

CREATE INDEX IF NOT EXISTS idx_audit_logs_occurred_at ON audit_logs (occurred_at DESC);
CREATE INDEX IF NOT EXISTS idx_audit_logs_table_name ON audit_logs (table_name);
CREATE INDEX IF NOT EXISTS idx_audit_logs_actor_user_id ON audit_logs (actor_user_id);

