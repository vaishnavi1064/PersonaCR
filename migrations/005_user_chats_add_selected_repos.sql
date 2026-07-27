-- PersonaCR: add selected_repos to user_chats
-- Mirrors backend/db/migrations/add_selected_repos.sql (do not edit that file).
-- Sources: frontend/src/lib/db.ts (updateChatSelectedRepos, loadChatSelectedRepos),
--          backend/db/migrations/add_selected_repos.sql

ALTER TABLE user_chats
  ADD COLUMN IF NOT EXISTS selected_repos jsonb DEFAULT '[]'::jsonb;

COMMENT ON COLUMN user_chats.selected_repos IS 'Array of repo_url strings selected as context for this chat conversation';
