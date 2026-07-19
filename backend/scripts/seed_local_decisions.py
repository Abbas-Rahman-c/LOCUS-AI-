"""
Seeds the local docker-compose Postgres (docker/init-local-schema.sql) with
the exact decisions the golden set was labeled against
(src/tests/fixtures/scenario_packs.json), then embeds each one via Voyage
-- so `scripts/run_rag_eval.py --pipeline real` has something real to
retrieve.

This is dev/eval tooling, not an application module: it opens its own
asyncpg pool rather than going through database.pool.get_db_pool()
(which requires the FastAPI lifespan to have run), and it defaults to the
docker-compose `db` service's host-published DSN rather than
backend/.env's DATABASE_URL (that .env value is for the real Supabase
instance; the local compose Postgres is a separate, disposable database).

Usage (from backend/, with the venv active and VOYAGE_API_KEY set):
    python scripts/seed_local_decisions.py
    python scripts/seed_local_decisions.py --database-url postgresql://...
    python scripts/seed_local_decisions.py --reset   # wipes seeded tables first

Idempotent: re-running with the same scenario_packs.json upserts (ON
CONFLICT DO UPDATE) rather than erroring on duplicate keys, so you can
re-run it after regenerating embeddings or editing the fixture.
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

import asyncpg

BACKEND_DIR = Path(__file__).resolve().parents[1]
SRC_DIR = BACKEND_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from common.config.voyage_config import get_voyage_config  # noqa: E402
from modules.ai.embeddings.provider import embed_document  # noqa: E402
from modules.retrieval.evaluation.golden_dataset import ScenarioPack, load_scenario_packs  # noqa: E402

DEFAULT_LOCAL_DSN = "postgresql://locus:locus_dev_password@localhost:5432/locus_dev"


def _searchable_text(statement: str, rationale: str | None) -> str:
    """Mirrors modules.ai.embeddings.service._build_searchable_text so
    locally-seeded embeddings are built the same way production embeddings
    are -- same input text convention in, comparable cosine scores out."""
    lines = [f"Decision: {statement}"]
    if rationale:
        lines.append(f"Rationale: {rationale}")
    return "\n".join(lines)


async def _reset(conn: asyncpg.Connection) -> None:
    print("Wiping decision_embeddings / decision_sources / decisions / tenants ...")
    await conn.execute("TRUNCATE public.decision_embeddings CASCADE")
    await conn.execute("TRUNCATE public.decision_sources CASCADE")
    await conn.execute("TRUNCATE public.decisions CASCADE")
    await conn.execute("TRUNCATE public.tenants CASCADE")


async def _seed_pack(conn: asyncpg.Connection, pack: ScenarioPack, embedding_model: str) -> int:
    await conn.execute(
        """
        INSERT INTO public.tenants (id, name, slug)
        VALUES ($1, $2, $3)
        ON CONFLICT (id) DO NOTHING
        """,
        pack.tenant_id,
        f"tenant-{str(pack.tenant_id)[:8]}",
        f"tenant-{str(pack.tenant_id)[:8]}",
    )

    embedded = 0
    for decision in pack.decisions:
        await conn.execute(
            """
            INSERT INTO public.decisions (
                id, tenant_id, record_type, decision_statement, rationale, status, confidence
            ) VALUES ($1, $2, $3, $4, $5, $6, $7)
            ON CONFLICT (id) DO UPDATE SET
                decision_statement = EXCLUDED.decision_statement,
                rationale = EXCLUDED.rationale,
                status = EXCLUDED.status
            """,
            decision.decision_id,
            decision.tenant_id,
            decision.record_type,
            decision.decision_statement,
            decision.rationale,
            decision.status,
            0.9,
        )

        if decision.source_permalink:
            await conn.execute(
                """
                INSERT INTO public.decision_sources (tenant_id, decision_id, permalink)
                VALUES ($1, $2, $3)
                ON CONFLICT (decision_id, permalink) DO NOTHING
                """,
                decision.tenant_id,
                decision.decision_id,
                decision.source_permalink,
            )

        text = _searchable_text(decision.decision_statement, decision.rationale)
        embedding = await embed_document(text)
        vector_literal = "[" + ",".join(str(x) for x in embedding) + "]"

        await conn.execute(
            """
            INSERT INTO public.decision_embeddings (decision_id, tenant_id, embedding, embedding_model)
            VALUES ($1, $2, $3::vector, $4)
            ON CONFLICT (decision_id) DO UPDATE SET
                embedding = EXCLUDED.embedding,
                embedding_model = EXCLUDED.embedding_model,
                embedded_at = now()
            """,
            decision.decision_id,
            decision.tenant_id,
            vector_literal,
            embedding_model,
        )
        embedded += 1

    return embedded


async def _main(database_url: str, scenario_packs_path: Path, reset: bool) -> None:
    packs = load_scenario_packs(scenario_packs_path)
    print(f"Loaded {len(packs)} scenario packs from {scenario_packs_path}")

    embedding_model = get_voyage_config().model

    pool = await asyncpg.create_pool(dsn=database_url, min_size=1, max_size=5)
    try:
        async with pool.acquire() as conn:
            if reset:
                await _reset(conn)

            total = 0
            for pack in packs:
                n = await _seed_pack(conn, pack, embedding_model)
                total += n
                print(f"  {pack.id} ({pack.source.value}/{pack.domain}): {n} decisions embedded")

        print(f"Done. {total} decisions seeded + embedded across {len(packs)} scenario packs.")
    finally:
        await pool.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed the local dev Postgres with golden-set scenario packs.")
    parser.add_argument("--database-url", default=DEFAULT_LOCAL_DSN, help="asyncpg DSN (default: local docker-compose db).")
    parser.add_argument(
        "--scenario-packs",
        type=Path,
        default=SRC_DIR / "tests" / "fixtures" / "scenario_packs.json",
    )
    parser.add_argument("--reset", action="store_true", help="Truncate seeded tables before inserting.")
    args = parser.parse_args()
    asyncio.run(_main(args.database_url, args.scenario_packs, args.reset))


if __name__ == "__main__":
    main()
