# RLS tenant isolation — apply & verify (after PR merge)

Do **not** run these against production until the `fix/rls-tenant-isolation` PR is accepted.

## 1. Apply SQL (as `postgres` / `DATABASE_URL`)

1. `backend/src/database/migrations/007_rls_tenant_isolation.sql`
2. `backend/src/database/migrations/008_create_locus_app_role.sql`
3. Set password: `alter role locus_app with password '<strong-password>';`
4. Set secrets:
   - Backend `.env`: `APP_DATABASE_URL` for `locus_app`
   - Keep `DATABASE_URL` as postgres
   - **Pooler username must be** `locus_app.<project-ref>` (e.g. `locus_app.imazdfzxinltbgktrgmv`),  
     same pattern as `postgres.<project-ref>`. Plain `locus_app` on the pooler causes `ENOIDENTIFIER`.
   - Or use direct: `postgresql://locus_app:...@db.<project-ref>.supabase.co:5432/postgres`

## 2. Verify

```powershell
cd backend
.\.venv\Scripts\Activate.ps1
$env:PYTHONPATH = "src"
python scripts/verify_rls_tenant_isolation.py
```

Expect `=== ALL CHECKS PASSED ===` (catalog FORCE/policies + cross-tenant actors isolation).
