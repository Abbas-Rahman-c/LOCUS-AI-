# RLS tenant isolation — apply & verify (after PR merge)

Do **not** run these against production until the `fix/rls-tenant-isolation` PR is accepted.

Full guide: `REF/Results/RLS_tenant_isolation_developer_guide.md`

## 1. Apply SQL (as `postgres` / `DATABASE_URL`)

1. `backend/src/database/migrations/007_rls_tenant_isolation.sql`
2. `backend/src/database/migrations/008_create_locus_app_role.sql`
3. Finish M8 role setup for `locus_app`.

## 2. Set `APP_DATABASE_URL`

Copy `DATABASE_URL`. Replace only the username role (`postgres…` → `locus_app…`).

**Example (pooler):**

```env
DATABASE_URL=postgresql://postgres.your-project-ref:<PASSWORD>@aws-0-us-west-1.pooler.supabase.com:6543/postgres?pgbouncer=true

APP_DATABASE_URL=postgresql://locus_app.your-project-ref:<PASSWORD>@aws-0-us-west-1.pooler.supabase.com:6543/postgres?pgbouncer=true
```

Keep `<PASSWORD>` exactly as in `DATABASE_URL`. On the pooler, username must be `locus_app.<project-ref>` (not plain `locus_app`).

Set the same on Edge secrets; redeploy Edge functions.

## 3. Verify

```powershell
cd backend
.\.venv\Scripts\Activate.ps1
$env:PYTHONPATH = "src"
python scripts/verify_rls_tenant_isolation.py
```

Expect `=== ALL CHECKS PASSED ===`.
