# Open items — unconfirmed from codebase

Schema below was inferred from TypeScript interfaces, insert/select payloads, and Python REST writers. Anything not listed in the migration files as a concrete column was **not invented**. Confirm against the live Supabase dashboard (SQL Editor → inspect) before treating this as authoritative.

## Constraints & indexes

| Item | Evidence | Status |
|------|----------|--------|
| `UNIQUE (fingerprints.repo_url)` | `cache_manager.save_fingerprint` does select-by-`repo_url` then update/insert | **Unconfirmed** — logic works without a unique constraint; uniqueness is likely intended |
| Unique `(user_id, repo_url)` on `user_repos` | `saveRepo` always inserts; duplicates possible | **Unconfirmed** |
| Indexes on `user_id`, `repo_url`, `created_at`, `analyzed_at`, `updated_at` | Filtered/ordered in queries | **Unconfirmed** — no `CREATE INDEX` in repo |
| Foreign keys to `auth.users(id)` | `user_id` comes from Supabase Auth UUID | **Unconfirmed** — common pattern, not referenced in app SQL |
| `NOT NULL` on optional text/score columns | Inserts often omit nullability intent | Partially assumed; tighten after dashboard inspect |

## Columns possibly present but never read/written in code

| Table | Column | Notes |
|-------|--------|-------|
| `fingerprints` | `created_at` | Only `updated_at` is written; `created_at` may exist with a default |
| `user_chats` | `created_at` | Only `updated_at` is selected/updated |
| `user_reviews` / `user_repos` / `user_chats` | Extra dashboard-only columns | Unknown |

## Columns present in code but weakly typed

| Column | Assumption in migrations | Why uncertain |
|--------|---------------------------|---------------|
| Score columns (`overall_score`, `style_score`, …) | `double precision` | TS `number` / Python `float`; could be `numeric` |
| `user_repos.languages` | `text[]` | docs/PROJECT_OVERVIEW + fingerprints use `text[]`; frontend sends JS arrays (PostgREST accepts both `text[]` and jsonb) |
| `user_chats.selected_repos` | `jsonb` | Confirmed by `backend/db/migrations/add_selected_repos.sql` |
| `id` defaults | `gen_random_uuid()` via `pgcrypto` | Standard Supabase; dashboard might use `uuid_generate_v4()` |

## RLS / policies

| Item | Status |
|------|--------|
| Row Level Security enabled? | **Unknown** — docs/PROJECT_OVERVIEW notes unclear RLS implications of frontend-vs-backend write split |
| Policies (`auth.uid() = user_id`, service-role bypass, etc.) | **Unknown** — no policy SQL in repo |
| Grants for `anon` / `authenticated` / `service_role` | **Unknown** |

## Behavioral notes (not schema bugs, but relevant)

1. **`last_repo_url`** — selected in `ChatMeta` / `loadChats`, and used as backfill source for `primary_repo_url` in `006`, but **no current TypeScript writer** sets `last_repo_url`. May be legacy or set only via dashboard/manual SQL.
2. **`analyzed_at` / `created_at` defaults** — `saveRepo` / `saveReview` omit these fields; migrations assume `DEFAULT now()`. If the live table lacks defaults, inserts would fail or leave nulls (ordering would break).
3. **Guest users** — guest IDs are `guest_<uuid>` strings. Chat/review/repo persistence to Supabase only runs when `session.user.id` exists, so guest strings should not hit UUID columns. Fingerprints may store `user_id = NULL` for anonymous.
4. **ChromaDB** — vector collections are local/filesystem, not Postgres tables; out of scope.
5. **Auth tables** — `auth.users` and related Supabase Auth schema are managed by Supabase; not duplicated here.

## Sources consulted

- `frontend/src/lib/db.ts`
- `backend/src/core/cache_manager.py`
- `backend/src/db/supabase_rest.py`
- `backend/src/agents/insights_agent.py`
- `backend/db/migrations/add_selected_repos.sql`
- `backend/db/migrations/add_primary_repo_url.sql`
- `docs/PROJECT_OVERVIEW.md` §4d
- `backend/requirements.txt` (no SQLAlchemy / Alembic)
