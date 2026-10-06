-- PersonaCR: fingerprints is service-role only
-- Only the backend (service_role, which bypasses RLS) reads or writes fingerprints;
-- the browser gets them through GET /api/repos. RLS on with no policies denies
-- every row to anon and authenticated, and the revoke removes table access outright.
-- Idempotent: safe to re-run.

BEGIN;

ALTER TABLE public.fingerprints ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON TABLE public.fingerprints FROM anon, authenticated;

-- Drop any policy left over from the dashboard era so nothing re-opens access.
DO $$
DECLARE p record;
BEGIN
  FOR p IN SELECT policyname FROM pg_policies WHERE schemaname = 'public' AND tablename = 'fingerprints' LOOP
    EXECUTE format('DROP POLICY %I ON public.fingerprints', p.policyname);
  END LOOP;
END $$;

COMMIT;

-- Rollback (manual):
--   ALTER TABLE public.fingerprints DISABLE ROW LEVEL SECURITY;
--   GRANT ALL ON TABLE public.fingerprints TO anon, authenticated;
