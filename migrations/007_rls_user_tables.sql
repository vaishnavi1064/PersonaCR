-- PersonaCR: Row Level Security on per-user tables
-- user_reviews, user_repos, user_chats: a signed-in user reads and writes only
-- rows whose user_id is their own auth.uid().
--
-- Who is affected:
--   authenticated  — GitHub users AND guests (Supabase anonymous sign-in; same role,
--                    JWT claim is_anonymous=true). Own rows only.
--   anon           — the bare anon key with no user session. No access at all.
--   service_role   — the backend. Bypasses RLS; unaffected.
--
-- Requires user_id to be uuid in all three tables. The live user_reviews and
-- user_repos columns were text until 009 converted them; 007 was first applied
-- with ::text casts, and 009 recreated these policies in exactly this form.
--
-- The update policy's WITH CHECK also stops a user re-assigning a row to someone else.
-- (select auth.uid()) is evaluated once per statement, not once per row.
-- Idempotent: safe to re-run.

BEGIN;

-- Permissive policies are OR-ed: one leftover "allow all" policy from the dashboard
-- would defeat everything below. Drop every existing policy on these tables first.
DO $$
DECLARE p record;
BEGIN
  FOR p IN SELECT tablename, policyname FROM pg_policies
           WHERE schemaname = 'public' AND tablename IN ('user_reviews', 'user_repos', 'user_chats') LOOP
    EXECUTE format('DROP POLICY %I ON public.%I', p.policyname, p.tablename);
  END LOOP;
END $$;

-- ── user_reviews ─────────────────────────────────────────────────────────────
ALTER TABLE public.user_reviews ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON TABLE public.user_reviews FROM anon, authenticated;
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE public.user_reviews TO authenticated;

CREATE POLICY user_reviews_select_own ON public.user_reviews
  FOR SELECT TO authenticated USING ((SELECT auth.uid()) = user_id);
CREATE POLICY user_reviews_insert_own ON public.user_reviews
  FOR INSERT TO authenticated WITH CHECK ((SELECT auth.uid()) = user_id);
CREATE POLICY user_reviews_update_own ON public.user_reviews
  FOR UPDATE TO authenticated USING ((SELECT auth.uid()) = user_id) WITH CHECK ((SELECT auth.uid()) = user_id);
CREATE POLICY user_reviews_delete_own ON public.user_reviews
  FOR DELETE TO authenticated USING ((SELECT auth.uid()) = user_id);

CREATE INDEX IF NOT EXISTS user_reviews_user_id_idx ON public.user_reviews (user_id);

-- ── user_repos ───────────────────────────────────────────────────────────────
ALTER TABLE public.user_repos ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON TABLE public.user_repos FROM anon, authenticated;
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE public.user_repos TO authenticated;

CREATE POLICY user_repos_select_own ON public.user_repos
  FOR SELECT TO authenticated USING ((SELECT auth.uid()) = user_id);
CREATE POLICY user_repos_insert_own ON public.user_repos
  FOR INSERT TO authenticated WITH CHECK ((SELECT auth.uid()) = user_id);
CREATE POLICY user_repos_update_own ON public.user_repos
  FOR UPDATE TO authenticated USING ((SELECT auth.uid()) = user_id) WITH CHECK ((SELECT auth.uid()) = user_id);
CREATE POLICY user_repos_delete_own ON public.user_repos
  FOR DELETE TO authenticated USING ((SELECT auth.uid()) = user_id);

CREATE INDEX IF NOT EXISTS user_repos_user_id_idx ON public.user_repos (user_id);

-- ── user_chats ───────────────────────────────────────────────────────────────
ALTER TABLE public.user_chats ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON TABLE public.user_chats FROM anon, authenticated;
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE public.user_chats TO authenticated;

CREATE POLICY user_chats_select_own ON public.user_chats
  FOR SELECT TO authenticated USING ((SELECT auth.uid()) = user_id);
CREATE POLICY user_chats_insert_own ON public.user_chats
  FOR INSERT TO authenticated WITH CHECK ((SELECT auth.uid()) = user_id);
CREATE POLICY user_chats_update_own ON public.user_chats
  FOR UPDATE TO authenticated USING ((SELECT auth.uid()) = user_id) WITH CHECK ((SELECT auth.uid()) = user_id);
CREATE POLICY user_chats_delete_own ON public.user_chats
  FOR DELETE TO authenticated USING ((SELECT auth.uid()) = user_id);

CREATE INDEX IF NOT EXISTS user_chats_user_id_idx ON public.user_chats (user_id);

COMMIT;

-- Rollback (manual):
--   ALTER TABLE public.<table> DISABLE ROW LEVEL SECURITY;
--   DROP POLICY <table>_{select,insert,update,delete}_own ON public.<table>;
--   GRANT ALL ON TABLE public.<table> TO anon, authenticated;
