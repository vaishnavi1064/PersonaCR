-- Migration: Add selected_repos column to user_chats
-- Run this in the Supabase SQL Editor before using the conversational Q&A feature.
-- This column stores the list of repo URLs selected for context in each chat session.

ALTER TABLE user_chats
ADD COLUMN IF NOT EXISTS selected_repos jsonb DEFAULT '[]'::jsonb;

COMMENT ON COLUMN user_chats.selected_repos IS 'Array of repo_url strings selected as context for this chat conversation';
