ALTER TABLE user_chats
  ADD COLUMN IF NOT EXISTS primary_repo_url text DEFAULT NULL;

-- Backfill primary_repo_url from last_repo_url for existing rows
UPDATE user_chats
  SET primary_repo_url = last_repo_url
  WHERE primary_repo_url IS NULL AND last_repo_url IS NOT NULL;
