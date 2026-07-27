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

`005` / `006` mirror the incremental scripts already under `backend/db/migrations/` (left untouched by this lane).

## Tables

| Table | Written by | Read by |
|-------|------------|---------|
| `fingerprints` | Backend `cache_manager.py` (service role) | Backend insights / review / cache |
| `user_reviews` | Frontend `lib/db.ts::saveReview` | Frontend dashboard; backend insights |
| `user_repos` | Frontend `lib/db.ts::saveRepo` | Frontend repo selector / dashboard |
| `user_chats` | Frontend `lib/db.ts` chat helpers | Frontend ChatPage / Sidebar |

See `OPEN_ITEMS.md` for columns, constraints, RLS, and indexes that could not be confirmed from the codebase.
