# PersonaCR schema migrations

Ordered, reproducible SQL capturing the **current** Supabase PostgreSQL schema as inferred from application code.

**Do not apply these against the live PersonaCR Supabase project from CI or casually.** They exist for source control and local/repro environments. Schema historically lived only in the Supabase dashboard.

## Why plain SQL (not Alembic)

The backend uses a REST client (`backend/src/db/supabase_rest.py`) and Pydantic models — **not** SQLAlchemy. Plain ordered `.sql` files are the right fit.

## Apply order

Run in numeric order against an empty Postgres / local Supabase:

1. `001_create_fingerprints.sql`
2. `002_create_user_reviews.sql`
3. `003_create_user_repos.sql`
4. `004_create_user_chats.sql`
5. `005_user_chats_add_selected_repos.sql`
6. `006_user_chats_add_primary_repo_url.sql`
7. `007_rls_user_tables.sql` — RLS: each user reads/writes only their own `user_reviews` / `user_repos` / `user_chats` rows
8. `008_rls_fingerprints_service_only.sql` — RLS: `fingerprints` readable/writable by the backend (service role) only
9. `009_user_id_text_to_uuid.sql` — converts `user_reviews.user_id` / `user_repos.user_id` from `text` to `uuid` (live schema drift) and recreates the RLS policies as `auth.uid() = user_id`
10. `010_lock_unused_tables.sql` — locks the unused legacy tables `reviews`, `chat_messages`, `documentation`, `agent_traces` (RLS on, no policies, `anon` / `authenticated` access revoked; kept, not dropped)

`007`–`010` are idempotent and are meant to be run in the Supabase SQL editor. All four have been applied to the live project.

## `user_id` column types

| Table | `user_id` type | Null? | History |
|-------|----------------|-------|---------|
| `user_reviews` | uuid | NOT NULL | Live column was `text` (despite `002`); converted by `009` |
| `user_repos` | uuid | NOT NULL | Live column was `text` (despite `003`); converted by `009` |
| `user_chats` | uuid | NOT NULL | Always uuid (`004`) |
| `fingerprints` | uuid | nullable | NULL for guests/anonymous (`cache_manager.py`) |

Confirmed on the live project after `009` (2026-10-05): `information_schema` shows `uuid` for all three user tables, and `pg_policies` shows 12 policies, none with a `::text` cast. Before conversion both text columns held only uuid values (2 and 6 rows).

Notes:
- `007` was first applied with `::text` casts on both sides, because `uuid = text` has no operator. `009` recreated the policies in their current form (`(SELECT auth.uid()) = user_id`), which is what `007` now contains, so a fresh database built from `001`–`009` matches the live project.
- Guests are keyed `guest_<sub>` by the backend and never stored in these tables. RLS blocks such rows from the browser; `backend/src/db/supabase_rest.py` refuses them from the backend (service role bypasses RLS), and backend reads skip the lookup for guests (`tests/test_user_id_writes.py`).

`005` / `006` mirror the incremental scripts already under `backend/db/migrations/` (left untouched by this lane).

## Tables

| Table | Written by | Read by |
|-------|------------|---------|
| `fingerprints` | Backend `cache_manager.py` (service role) | Backend insights / review / cache |
| `user_reviews` | Frontend `lib/db.ts::saveReview` | Frontend dashboard; backend insights |
| `user_repos` | Backend analyze worker (service role); frontend `lib/db.ts::saveRepo` (sync fallback) | Backend `GET /api/repos` |
| `user_chats` | Frontend `lib/db.ts` chat helpers | Frontend ChatPage / Sidebar |

See `OPEN_ITEMS.md` for columns, constraints, RLS, and indexes that could not be confirmed from the codebase.
