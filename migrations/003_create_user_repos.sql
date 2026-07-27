-- PersonaCR: user_repos table
-- Sources: frontend/src/lib/db.ts (RepoRow, saveRepo, fetchRepos, getUserAnalyzedRepos)

CREATE EXTENSION IF NOT EXISTS "pgcrypto";

CREATE TABLE IF NOT EXISTS user_repos (
  id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id          uuid NOT NULL,                  -- session.user.id (auth UUID)
  repo_url         text NOT NULL,
  repo_name        text,
  functions_count  integer,
  languages        text[],                         -- string[] from frontend; PROJECT_OVERVIEW: text[]
  analyzed_at      timestamptz NOT NULL DEFAULT now()  -- not sent on insert; ordered DESC
);

COMMENT ON TABLE user_repos IS 'Repos a user has analyzed; written by frontend db.ts::saveRepo';
COMMENT ON COLUMN user_repos.languages IS 'Language names derived from fingerprint language_distribution keys';
