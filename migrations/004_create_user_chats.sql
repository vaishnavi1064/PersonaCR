-- PersonaCR: user_chats table (base columns)
-- Sources: frontend/src/lib/db.ts (ChatMeta, PersistedMessage, createChat / load / save)
-- Incremental columns selected_repos / primary_repo_url added in 005 and 006.

CREATE EXTENSION IF NOT EXISTS "pgcrypto";

CREATE TABLE IF NOT EXISTS user_chats (
  id             uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id        uuid NOT NULL,                    -- session.user.id (auth UUID)
  title          text NOT NULL DEFAULT 'New review',
  messages       jsonb NOT NULL DEFAULT '[]'::jsonb, -- PersistedMessage[]
  starred        boolean NOT NULL DEFAULT false,
  last_repo_url  text,                             -- selected in ChatMeta; no writer found in current code
  updated_at     timestamptz NOT NULL DEFAULT now()
);

COMMENT ON TABLE user_chats IS 'Per-user chat sessions with message history; written by frontend db.ts';
COMMENT ON COLUMN user_chats.messages IS 'JSON array of {role, content, type, data?, timestamp}';
COMMENT ON COLUMN user_chats.last_repo_url IS 'Nullable repo URL; read by UI but no current writer confirmed in codebase';
