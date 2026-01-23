# Supabase Local Backup/Restore (Large Dataset) — Excluding User Tables

This document summarizes the workflow we used to reliably back up and restore a large Supabase dataset (multi-GB) into **local Supabase**, while **excluding user-related tables**.

The key goals are:

- Restore **application data** (e.g. `court_cases`, `legislation`, embeddings, etc.).
- Avoid restoring **Supabase internal schemas** (`auth`, `storage`, etc.).
- Avoid restoring **user-related tables** in `public` that depend on `auth.users`.
- Avoid failures caused by huge `INSERT ... VALUES (...)` statements.

## Why not `supabase db reset` + `supabase/seed.sql`?

For large datasets, `supabase/seed.sql` is not suitable. The Supabase CLI may attempt to send the seed as a large batch, leading to failures like:

- `failed to send batch: message body too large`

## Overview of the recommended approach

- Use `pg_dump` in **custom format** (`-Fc`) and restore with `pg_restore`.
- Dump **data-only** from the source DB.
- Limit the dump to the `public` schema.
- Exclude user-related tables from the dump.
- Reset the local DB with migrations, truncate `public` tables, then restore.

## User-related tables to exclude

In this project, user profile tables live in `public` and depend on `auth.users`.

From `supabase/migrations/20260117031242_add_user_management.sql`:

- `public.user_profiles` has `id UUID PRIMARY KEY REFERENCES auth.users(id)`.

Tables to exclude:

- `public.user_profiles`
- `public.user_searches`
- `public.user_collections`
- `public.collection_items`

If you restore these without also restoring `auth.users`, you will see FK failures like:

- `violates foreign key constraint "user_profiles_id_fkey" ... Key (id) is not present in table "users"`

## Prerequisites

- Postgres client tools installed on both machines:
  - `pg_dump` on the **source** machine
  - `pg_restore` and `psql` on the **destination** machine
- Ensure the Postgres client major version is compatible with the server (use Postgres 17 tools if your DB is Postgres 17).

## 1) Create the dump on the source machine

Set your source DB URL (examples):

```bash
export SOURCE_DB_URL="postgresql://postgres:postgres@127.0.0.1:34322/postgres"
```

Create a **custom-format**, **data-only**, **public-only** dump, excluding user tables:

```bash
pg_dump "$SOURCE_DB_URL" \
  -Fc \
  --data-only \
  --no-owner \
  --no-privileges \
  --schema=public \
  --exclude-table=public.user_profiles \
  --exclude-table=public.user_searches \
  --exclude-table=public.user_collections \
  --exclude-table=public.collection_items \
  -f seed_public_no_users.dump
```

Notes:

- `-Fc` produces an archive that `pg_restore` can restore reliably and efficiently.
- `--schema=public` prevents dumping Supabase internal schemas.
- Excluding user tables avoids FK failures caused by `auth.users` not being present.

## 2) Copy the dump to your local machine

Example:

```bash
scp seed_public_no_users.dump <your-mac>:/path/to/Legal-AI/
```

Store it somewhere like:

- `supabase/seed_public_no_users.dump`

Also note the project `.gitignore` should ignore large dump files.

## 3) Prepare local Supabase DB (destination)

Use the DB URL printed by `supabase status`. Example local DB URL:

- `postgresql://postgres:postgres@127.0.0.1:34322/postgres`

### 3.1 Reset the local DB (apply migrations)

```bash
supabase db reset
```

This recreates the database and applies migrations.

### 3.2 Truncate all `public` tables

This ensures a clean target state and prevents duplicate-key errors.

```bash
psql "postgresql://postgres:postgres@127.0.0.1:34322/postgres" -v ON_ERROR_STOP=1 <<'SQL'
DO $$
DECLARE r record;
BEGIN
  FOR r IN
    SELECT tablename
    FROM pg_tables
    WHERE schemaname = 'public'
  LOOP
    EXECUTE format('TRUNCATE TABLE public.%I CASCADE', r.tablename);
  END LOOP;
END $$;
SQL
```

## 4) Restore into local Supabase

Restore using `pg_restore` (single job initially):

```bash
pg_restore \
  -d "postgresql://postgres:postgres@127.0.0.1:34322/postgres" \
  --data-only \
  --no-owner \
  --no-privileges \
  -j 1 \
  supabase/seed_public_no_users.dump
```

Notes:

- Start with `-j 1` (deterministic). If it succeeds and you want speed, try `-j 2` or `-j 4`.
- Do **not** use `--disable-triggers` with Supabase local. It attempts to disable system RI triggers and fails with:
  - `permission denied: "RI_ConstraintTrigger_..." is a system trigger`

## 5) Optional: TOC filtering (if you already have a dump that includes unwanted tables)

If you already produced a dump that includes user tables and want to exclude them at restore-time:

1. Generate a TOC list:

```bash
pg_restore -l seed_public.dump > seed_public.toc
```

1. Edit `seed_public.toc` and remove the `TABLE DATA` entries for:

- `public user_profiles`
- `public user_searches`
- `public user_collections`
- `public collection_items`

1. Restore using the filtered TOC:

```bash
pg_restore \
  -d "postgresql://postgres:postgres@127.0.0.1:34322/postgres" \
  --data-only \
  --no-owner \
  --no-privileges \
  -j 1 \
  -L seed_public.toc \
  seed_public.dump
```

## Troubleshooting

### Duplicate key errors

If you see errors like `duplicate key value violates unique constraint ...`, it usually means you are restoring into a non-empty table.

Fix:

- rerun the truncate step in section 3.2

### FK violations (parent rows missing)

If you still see FK errors after excluding user tables, restore in stages by table:

- restore parent tables first (`courts`, `legislation`, etc.)
- then restore child tables (`court_cases`, `legislation_sections`, etc.)

### Extremely slow restore

If restore is slow:

- keep `-j 1` for reliability, then gradually increase
- consider dropping and recreating heavy indexes (e.g. large GIN full-text indexes) after the load

## Rules followed

- **Meta Rule**: explicitly state rules being followed.
- **Core Development Principles**: prefer robust and repeatable restore procedures over brittle manual splitting.
- **Security**: avoid treating auth/user tables as part of the bulk dataset restore.
