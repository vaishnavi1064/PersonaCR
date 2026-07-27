-- PersonaCR: user_reviews table
-- Sources: frontend/src/lib/db.ts (ReviewRow, saveReview, fetchReviews),
--          backend/src/agents/insights_agent.py (_load_recent_reviews)

CREATE EXTENSION IF NOT EXISTS "pgcrypto";

CREATE TABLE IF NOT EXISTS user_reviews (
  id                uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id           uuid NOT NULL,                 -- session.user.id (auth UUID)
  repo_url          text NOT NULL,
  repo_name         text,
  submitted_code    text,                          -- truncated to 500 chars on insert
  overall_score     double precision,
  style_score       double precision,
  defect_score      double precision,
  comprehensiveness double precision,              -- STS / quality score (0–1 range in UI math)
  conciseness       double precision,
  relevance         double precision,
  issues_count      integer,
  issues            jsonb DEFAULT '[]'::jsonb,     -- IssueRow[]
  status            text,                          -- e.g. 'passed'
  agent_trace       jsonb DEFAULT '[]'::jsonb,     -- AgentTraceRow[]
  iterations        integer,
  created_at        timestamptz NOT NULL DEFAULT now()  -- not sent on insert; ordered DESC
);

COMMENT ON TABLE user_reviews IS 'Persisted code-review results; written by frontend db.ts::saveReview';
COMMENT ON COLUMN user_reviews.issues IS 'JSON array of {type, category?, severity?, description}';
COMMENT ON COLUMN user_reviews.agent_trace IS 'JSON array of {agent_name, output_summary?, execution_time_ms?, iteration?}';
