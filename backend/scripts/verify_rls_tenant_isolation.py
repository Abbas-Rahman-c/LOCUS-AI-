"""
Step 5 — Verify tenant row-level security isolation.

Run AFTER M7 + M8 are applied to the target database and APP_DATABASE_URL
points at locus_app (non-bypass). Do NOT run against production until the
RLS PR is accepted and migrations are applied.

Usage (from backend/ with venv):

  set PYTHONPATH=src
  python scripts/verify_rls_tenant_isolation.py

Requires in backend/.env:
  DATABASE_URL      — postgres (admin), used only to seed two test tenants
  APP_DATABASE_URL  — locus_app, used for isolation assertions
"""
from __future__ import annotations

import asyncio
import os
import sys
import uuid
from pathlib import Path

import asyncpg
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

TENANT_TABLES = (
    "actors",
    "source_connections",
    "raw_events",
    "decisions",
    "decision_actors",
    "decision_sources",
    "decision_embeddings",
    "mcp_tool_calls",
    "tenants",
    "memberships",
)


def _require(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise SystemExit(f"Missing {name} in backend/.env")
    return value.replace("postgresql+asyncpg://", "postgresql://")


async def _catalog_check(admin: asyncpg.Connection) -> None:
    print("=== Catalog: RLS + policies on public tenant tables ===")
    rows = await admin.fetch(
        """
        select c.relname as table_name,
               c.relrowsecurity as rls_enabled,
               c.relforcerowsecurity as rls_forced,
               coalesce((
                 select count(*) from pg_policies p
                 where p.schemaname = 'public' and p.tablename = c.relname
               ), 0) as policy_count
        from pg_class c
        join pg_namespace n on n.oid = c.relnamespace
        where n.nspname = 'public'
          and c.relkind = 'r'
          and c.relname = any($1::text[])
        order by c.relname
        """,
        list(TENANT_TABLES),
    )
    failed = False
    for row in rows:
        ok = row["rls_enabled"] and row["rls_forced"] and row["policy_count"] >= 1
        mark = "OK" if ok else "FAIL"
        print(
            f"  [{mark}] {row['table_name']}: "
            f"rls={row['rls_enabled']} force={row['rls_forced']} "
            f"policies={row['policy_count']}"
        )
        if not ok:
            failed = True
    if failed:
        raise SystemExit(
            "Catalog check failed — apply M7 (007_rls_tenant_isolation.sql) first"
        )

    bypass = await admin.fetchval(
        """
        select rolbypassrls from pg_roles where rolname = 'locus_app'
        """
    )
    if bypass is None:
        raise SystemExit("Role locus_app missing — apply M8 (008_create_locus_app_role.sql)")
    if bypass is True:
        raise SystemExit("locus_app still has rolbypassrls=true — fix M8 / ALTER ROLE")
    print("  [OK] locus_app exists and rolbypassrls=false")


async def _isolation_check(admin: asyncpg.Connection, app_dsn: str) -> None:
    print("=== Isolation: locus_app cannot see other tenant rows ===")
    tenant_a = uuid.uuid4()
    tenant_b = uuid.uuid4()
    slug_a = f"rls-verify-a-{tenant_a.hex[:8]}"
    slug_b = f"rls-verify-b-{tenant_b.hex[:8]}"

    await admin.execute(
        """
        insert into public.tenants (id, name, slug, plan)
        values
          ($1, 'RLS Verify A', $2, 'self_serve'),
          ($3, 'RLS Verify B', $4, 'self_serve')
        """,
        tenant_a,
        slug_a,
        tenant_b,
        slug_b,
    )
    await admin.execute(
        """
        insert into public.actors (tenant_id, display_name, email, kind)
        values
          ($1, 'Actor A', $2, 'internal'),
          ($3, 'Actor B', $4, 'internal')
        """,
        tenant_a,
        f"a-{tenant_a.hex[:8]}@example.com",
        tenant_b,
        f"b-{tenant_b.hex[:8]}@example.com",
    )

    try:
        app = await asyncpg.connect(app_dsn, statement_cache_size=0)
    except Exception as exc:
        msg = str(exc)
        if "ENOIDENTIFIER" in msg or "tenant identifier" in msg.lower():
            raise SystemExit(
                "Failed to connect as locus_app via the pooler.\n"
                "Derive APP_DATABASE_URL from DATABASE_URL by replacing only the "
                "role in the username:\n"
                "  pooler: postgres.<project-ref> → locus_app.<project-ref>\n"
                "  direct: postgres → locus_app\n"
                "Plain locus_app (no .<project-ref>) on the pooler causes this error.\n"
                f"Original error: {exc}"
            ) from exc
        raise

    try:
        # As A: should see only A's actor
        await app.execute(
            "select set_config('app.current_tenant_id', $1, false)",
            str(tenant_a),
        )
        count_a = await app.fetchval(
            "select count(*) from public.actors where tenant_id = any($1::uuid[])",
            [tenant_a, tenant_b],
        )
        names_a = await app.fetch(
            "select display_name from public.actors order by display_name"
        )

        # As B: should see only B's actor
        await app.execute(
            "select set_config('app.current_tenant_id', $1, false)",
            str(tenant_b),
        )
        count_b = await app.fetchval(
            "select count(*) from public.actors where tenant_id = any($1::uuid[])",
            [tenant_a, tenant_b],
        )
        names_b = await app.fetch(
            "select display_name from public.actors order by display_name"
        )

        print(f"  tenant A context: count={count_a} names={[r['display_name'] for r in names_a]}")
        print(f"  tenant B context: count={count_b} names={[r['display_name'] for r in names_b]}")

        if count_a != 1 or [r["display_name"] for r in names_a] != ["Actor A"]:
            raise SystemExit("FAIL: tenant A context leaked or missed rows")
        if count_b != 1 or [r["display_name"] for r in names_b] != ["Actor B"]:
            raise SystemExit("FAIL: tenant B context leaked or missed rows")

        # Negative: A cannot update B's row
        await app.execute(
            "select set_config('app.current_tenant_id', $1, false)",
            str(tenant_a),
        )
        updated = await app.execute(
            "update public.actors set display_name = 'HACKED' where tenant_id = $1",
            tenant_b,
        )
        # asyncpg returns e.g. "UPDATE 0"
        if updated.split()[-1] != "0":
            raise SystemExit(f"FAIL: tenant A updated tenant B rows ({updated})")
        print("  [OK] tenant A UPDATE on tenant B affected 0 rows")

        print("  [OK] cross-tenant isolation holds for actors")
    finally:
        await app.close()
        await admin.execute(
            "delete from public.tenants where id = any($1::uuid[])",
            [tenant_a, tenant_b],
        )
        print("  cleaned up verify tenants")


async def main() -> None:
    admin_dsn = _require("DATABASE_URL")
    app_dsn = _require("APP_DATABASE_URL")

    if admin_dsn == app_dsn:
        print(
            "WARNING: DATABASE_URL and APP_DATABASE_URL are identical — "
            "isolation test is meaningless if both bypass RLS.",
            file=sys.stderr,
        )

    admin = await asyncpg.connect(admin_dsn, statement_cache_size=0)
    try:
        await _catalog_check(admin)
        await _isolation_check(admin, app_dsn)
    finally:
        await admin.close()

    print("=== ALL CHECKS PASSED ===")


if __name__ == "__main__":
    asyncio.run(main())
