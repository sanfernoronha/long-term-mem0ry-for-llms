-- init.sql
CREATE TABLE IF NOT EXISTS memory_metadata (
    id SERIAL PRIMARY KEY,
    memory_id UUID NOT NULL UNIQUE,
    user_id VARCHAR(255) NOT NULL,
    text TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
