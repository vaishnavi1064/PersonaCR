-- PersonaCR: add primary_repo_url to user_chats
-- Mirrors backend/db/migrations/add_primary_repo_url.sql (do not edit that file).
-- Sources: frontend/src/lib/db.ts (updateChatPrimaryRepoUrl),
--          backend/db/migrations/add_primary_repo_url.sql

ALTER TABLE user_chats
  ADD COLUMN IF NOT EXISTS primary_repo_url text DEFAULT NULL;

-- Backfill from last_repo_url for existing rows (same as backend migration)
UPDATE user_chats
  SET primary_repo_url = last_repo_url
  WHERE primary_repo_url IS NULL AND last_repo_url IS NOT NULL;

COMMENT ON COLUMN user_chats.primary_repo_url IS 'Primary repo used for code review context in this chat';
