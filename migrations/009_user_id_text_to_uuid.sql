-- PersonaCR: user_reviews.user_id and user_repos.user_id  text → uuid
-- The live columns were created as text (002/003 always intended uuid; user_chats
-- already is). After this, all three user tables store user_id as uuid, and RLS
-- compares auth.uid() = user_id directly — no casts.
--
-- Postgres refuses to change the type of a column a policy depends on, so the
-- policies on these tables are dropped, the columns converted, and the policies
-- recreated. The user_id indexes from 007 are rebuilt by ALTER ... TYPE itself.
-- user_chats' column doesn't change, but its policies are recreated without the
-- ::text cast so all three tables match migrations/007.
--
-- On a fresh database (002/003 already create uuid columns) this is a no-op apart
-- from recreating the policies; the ::text in the pre-check keeps it valid there.
--
-- One transaction: any failure (e.g. a non-uuid value) rolls everything back.
-- Takes a brief ACCESS EXCLUSIVE lock on the three tables (they're small).

BEGIN;

-- Refuse up front, with a readable error, if any stored value isn't a uuid.
DO $$
DECLARE
  uuid_re constant text := '^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$';
  bad bigint;
BEGIN
  SELECT count(*) INTO bad FROM public.user_reviews WHERE user_id::text !~* uuid_re;
  IF bad > 0 THEN RAISE EXCEPTION 'user_reviews has % row(s) whose user_id is not a uuid', bad; END IF;
  SELECT count(*) INTO bad FROM public.user_repos WHERE user_id::text !~* uuid_re;
  IF bad > 0 THEN RAISE EXCEPTION 'user_repos has % row(s) whose user_id is not a uuid', bad; END IF;
END $$;

-- Drop every policy on the three tables (007's, plus anything else that would block the ALTER).
DO $$
DECLARE p record;
BEGIN
  FOR p IN SELECT tablename, policyname FROM pg_policies
           WHERE schemaname = 'public' AND tablename IN ('user_reviews', 'user_repos', 'user_chats') LOOP
    EXECUTE format('DROP POLICY %I ON public.%I', p.policyname, p.tablename);
  END LOOP;
END $$;

ALTER TABLE public.user_reviews ALTER COLUMN user_id TYPE uuid USING user_id::uuid;
ALTER TABLE public.user_repos   ALTER COLUMN user_id TYPE uuid USING user_id::uuid;

-- ── policies: own rows only, uuid = uuid ─────────────────────────────────────
CREATE POLICY user_reviews_select_own ON public.user_reviews
  FOR SELECT TO authenticated USING ((SELECT auth.uid()) = user_id);
CREATE POLICY user_reviews_insert_own ON public.user_reviews
  FOR INSERT TO authenticated WITH CHECK ((SELECT auth.uid()) = user_id);
CREATE POLICY user_reviews_update_own ON public.user_reviews
  FOR UPDATE TO authenticated USING ((SELECT auth.uid()) = user_id) WITH CHECK ((SELECT auth.uid()) = user_id);
CREATE POLICY user_reviews_delete_own ON public.user_reviews
  FOR DELETE TO authenticated USING ((SELECT auth.uid()) = user_id);

CREATE POLICY user_repos_select_own ON public.user_repos
  FOR SELECT TO authenticated USING ((SELECT auth.uid()) = user_id);
CREATE POLICY user_repos_insert_own ON public.user_repos
  FOR INSERT TO authenticated WITH CHECK ((SELECT auth.uid()) = user_id);
CREATE POLICY user_repos_update_own ON public.user_repos
  FOR UPDATE TO authenticated USING ((SELECT auth.uid()) = user_id) WITH CHECK ((SELECT auth.uid()) = user_id);
CREATE POLICY user_repos_delete_own ON public.user_repos
  FOR DELETE TO authenticated USING ((SELECT auth.uid()) = user_id);

CREATE POLICY user_chats_select_own ON public.user_chats
  FOR SELECT TO authenticated USING ((SELECT auth.uid()) = user_id);
CREATE POLICY user_chats_insert_own ON public.user_chats
  FOR INSERT TO authenticated WITH CHECK ((SELECT auth.uid()) = user_id);
CREATE POLICY user_chats_update_own ON public.user_chats
  FOR UPDATE TO authenticated USING ((SELECT auth.uid()) = user_id) WITH CHECK ((SELECT auth.uid()) = user_id);
CREATE POLICY user_chats_delete_own ON public.user_chats
  FOR DELETE TO authenticated USING ((SELECT auth.uid()) = user_id);

COMMIT;

-- Verify (read-only):
--   SELECT table_name, data_type FROM information_schema.columns
--    WHERE table_schema = 'public' AND column_name = 'user_id'
--      AND table_name IN ('user_reviews', 'user_repos', 'user_chats');
--   SELECT tablename, policyname, qual, with_check FROM pg_policies
--    WHERE schemaname = 'public' AND tablename IN ('user_reviews', 'user_repos', 'user_chats')
--    ORDER BY tablename, policyname;
--
-- Rollback (manual; re-creates the text columns and 007's text-cast policies):
--   drop the policies, then ALTER TABLE ... ALTER COLUMN user_id TYPE text USING user_id::text;
--   and re-run the pre-009 version of 007.
