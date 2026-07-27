-- PersonaCR: fingerprints table
-- Sources: backend/src/core/cache_manager.py, backend/src/agents/insights_agent.py
-- Backend upserts by looking up repo_url then insert/update (service role REST).

CREATE EXTENSION IF NOT EXISTS "pgcrypto";

CREATE TABLE IF NOT EXISTS fingerprints (
  id                uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id           uuid,                          -- UUID or NULL (anonymous → NULL in cache_manager)
  repo_url          text NOT NULL,
  repo_name         text,
  fingerprint_data  jsonb,
  num_functions     integer,
  languages         text[],                        -- written as PG array via REST
  last_commit_sha   text,
  updated_at        timestamptz
);

COMMENT ON TABLE fingerprints IS 'SHA-cached coding-style fingerprints per repo; written by backend cache_manager';
COMMENT ON COLUMN fingerprints.user_id IS 'Supabase auth user UUID; NULL when user_id is anonymous';
COMMENT ON COLUMN fingerprints.fingerprint_data IS 'JSON blob of FingerprintData fields (avg_function_length, naming_convention, etc.)';
COMMENT ON COLUMN fingerprints.languages IS 'PostgreSQL text[] of language names';
COMMENT ON COLUMN fingerprints.last_commit_sha IS 'Default-branch HEAD SHA used for cache freshness';
