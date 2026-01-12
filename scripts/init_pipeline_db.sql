-- Spec Pipeline Orchestrator Database Schema
-- PostgreSQL tables for checkpoint/resume functionality

-- Pipeline runs (main table)
CREATE TABLE IF NOT EXISTS spec_pipeline_runs (
    run_id UUID PRIMARY KEY,
    project VARCHAR(255) NOT NULL,
    feature_description TEXT NOT NULL,
    current_state VARCHAR(50) NOT NULL DEFAULT 'not_started',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    completed_at TIMESTAMP WITH TIME ZONE,
    metadata JSONB DEFAULT '{}'::jsonb,

    -- Index for common queries
    CONSTRAINT valid_state CHECK (current_state IN (
        'not_started', 'constitution', 'spec_created', 'checklist_done',
        'clarified', 'researched', 'plan_created', 'tasks_created',
        'analyzed', 'issues_created', 'verified', 'synced',
        'completed', 'failed'
    ))
);

-- Individual step tracking
CREATE TABLE IF NOT EXISTS spec_pipeline_steps (
    id SERIAL PRIMARY KEY,
    run_id UUID NOT NULL REFERENCES spec_pipeline_runs(run_id) ON DELETE CASCADE,
    step_name VARCHAR(50) NOT NULL,
    step_order INT NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'pending',
    started_at TIMESTAMP WITH TIME ZONE,
    completed_at TIMESTAMP WITH TIME ZONE,
    duration_ms BIGINT,
    error_message TEXT,
    retry_count INT DEFAULT 0,
    skipped_reason TEXT,
    output_summary TEXT,

    CONSTRAINT valid_status CHECK (status IN ('pending', 'running', 'completed', 'failed', 'skipped')),
    CONSTRAINT unique_step_per_run UNIQUE (run_id, step_name)
);

-- Circuit breaker state (for external services)
CREATE TABLE IF NOT EXISTS spec_pipeline_circuit_breaker (
    service_name VARCHAR(50) PRIMARY KEY,
    state VARCHAR(20) NOT NULL DEFAULT 'closed',
    failure_count INT DEFAULT 0,
    last_failure_at TIMESTAMP WITH TIME ZONE,
    last_success_at TIMESTAMP WITH TIME ZONE,
    opened_at TIMESTAMP WITH TIME ZONE,
    half_open_at TIMESTAMP WITH TIME ZONE,

    CONSTRAINT valid_cb_state CHECK (state IN ('closed', 'open', 'half_open'))
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_pipeline_runs_project ON spec_pipeline_runs(project);
CREATE INDEX IF NOT EXISTS idx_pipeline_runs_state ON spec_pipeline_runs(current_state);
CREATE INDEX IF NOT EXISTS idx_pipeline_runs_created ON spec_pipeline_runs(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_pipeline_steps_run_id ON spec_pipeline_steps(run_id);
CREATE INDEX IF NOT EXISTS idx_pipeline_steps_status ON spec_pipeline_steps(status);

-- Update timestamp trigger
CREATE OR REPLACE FUNCTION update_pipeline_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS update_pipeline_runs_timestamp ON spec_pipeline_runs;
CREATE TRIGGER update_pipeline_runs_timestamp
    BEFORE UPDATE ON spec_pipeline_runs
    FOR EACH ROW
    EXECUTE FUNCTION update_pipeline_timestamp();

-- Initialize circuit breaker for known services
INSERT INTO spec_pipeline_circuit_breaker (service_name, state)
VALUES
    ('github', 'closed'),
    ('n8n', 'closed'),
    ('context7', 'closed'),
    ('questdb', 'closed')
ON CONFLICT (service_name) DO NOTHING;

-- QuestDB table for metrics (run separately on QuestDB)
-- CREATE TABLE spec_pipeline_metrics (
--     timestamp TIMESTAMP,
--     run_id SYMBOL,
--     project SYMBOL,
--     step_name SYMBOL,
--     duration_ms LONG,
--     status SYMBOL,
--     retry_count INT,
--     error_type SYMBOL
-- ) timestamp(timestamp) PARTITION BY DAY;
