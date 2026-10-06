-- PersonaCR: lock the four unused legacy tables
-- reviews, chat_messages, documentation, agent_traces predate the user_* tables.
-- No code reads or writes them and they were empty (2026-10-05), but the anon key
-- still had table access. Kept (not dropped) — this only closes access:
--   RLS on with no policies  → no rows for anon / authenticated
--   REVOKE ALL               → no table privileges for anon / authenticated
--   service_role             → unchanged (bypasses RLS)
-- Each relation's kind is checked first: RLS applies to tables only, so a view
-- (if any of these is one) just gets the REVOKE. Missing relations are skipped.
-- Idempotent: safe to re-run.

BEGIN;

DO $$
DECLARE
  t text;
  kind "char";
  p record;
BEGIN
  FOREACH t IN ARRAY ARRAY['reviews', 'chat_messages', 'documentation', 'agent_traces'] LOOP
    SELECT c.relkind INTO kind
      FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
     WHERE n.nspname = 'public' AND c.relname = t;

    IF kind IS NULL THEN
      RAISE NOTICE 'public.% does not exist — skipped', t;
      CONTINUE;
    END IF;

    IF kind IN ('r', 'p') THEN  -- ordinary or partitioned table
      EXECUTE format('ALTER TABLE public.%I ENABLE ROW LEVEL SECURITY', t);
      FOR p IN SELECT policyname FROM pg_policies WHERE schemaname = 'public' AND tablename = t LOOP
        EXECUTE format('DROP POLICY %I ON public.%I', p.policyname, t);
      END LOOP;
    ELSE
      RAISE NOTICE 'public.% is not a table (relkind %) — revoking access only', t, kind;
    END IF;

    EXECUTE format('REVOKE ALL ON public.%I FROM anon, authenticated', t);
  END LOOP;
END $$;

COMMIT;

-- Verify (read-only): rls_enabled true, and no rows for anon/authenticated grants.
--   SELECT relname, relkind, relrowsecurity AS rls_enabled FROM pg_class
--    WHERE relnamespace = 'public'::regnamespace
--      AND relname IN ('reviews', 'chat_messages', 'documentation', 'agent_traces');
--   SELECT table_name, grantee, privilege_type FROM information_schema.role_table_grants
--    WHERE table_schema = 'public' AND grantee IN ('anon', 'authenticated')
--      AND table_name IN ('reviews', 'chat_messages', 'documentation', 'agent_traces');
--
-- Rollback (manual):
--   ALTER TABLE public.<table> DISABLE ROW LEVEL SECURITY;
--   GRANT ALL ON public.<table> TO anon, authenticated;
