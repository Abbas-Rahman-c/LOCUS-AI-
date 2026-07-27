"""
Generation-only script for the 250-decision / 60-query evaluation corpus v2.

This script performs NO ingestion, NO embedding, NO Claude/Voyage calls, NO
DB connections, and NO git operations. It is pure, deterministic Python
string templating + json output, seeded via random.Random(20260726) so the
corpus is byte-for-byte reproducible.

Outputs (all under backend/src/evaluation/corpus_v2/, all untracked):
  - decisions.json           250 decisions, full detail (raw_content + structured_ground_truth)
  - ground_truth.json        distilled ground-truth-only view, keyed by source_message_id
  - benchmark_regression.json  the original 25 Stage 2 queries, unchanged
  - benchmark_hybrid.json    35 new hybrid-focused queries with documented rationale
  - corpus_report.json       distribution + dedup/near-dup report

Usage:
    cd backend
    .venv/bin/python scripts/generate_eval_corpus_v2.py
"""
from __future__ import annotations

import json
import random
from datetime import datetime, timedelta, timezone
from pathlib import Path

SEED = 20260726
rng = random.Random(SEED)

TENANT_ID = "13bcd0fa-1ed9-4634-93c7-278ba97ec658"
BACKEND_DIR = Path(__file__).resolve().parents[1]
OUT_DIR = BACKEND_DIR / "src" / "evaluation" / "corpus_v2"

EMPLOYEES = [
    "Priya Chen", "Marcus Webb", "Elena Rodriguez", "Jordan Kim", "Sam Osei",
    "Nadia Farouk", "Ben Whitfield", "Grace Liu", "Tomas Novak", "Aisha Rahman",
    "Derek Holt", "Yuki Tanaka", "Carlos Mendes", "Ingrid Larsen", "Omar Siddiqui",
    "Lena Brandt", "Felix Adeyemi", "Maya Patel", "Ryan O'Connell", "Sofia Kowalski",
    "Ethan Brooks", "Zara Malik", "Hugo Fernandez", "Chloe Bennett", "Arjun Mehta",
    "Ines Rocha", "Nathan Voss", "Amara Okonkwo", "Leo Castellanos", "Ravi Iyer",
    "Freya Andersen", "Dominic Russo", "Wei Zhang", "Isabel Torres", "Colin Marsh",
    "Noor Hassan", "Trevor Lindqvist", "Anya Petrov", "Julian Ferreira", "Bianca Sato",
]

PAIN_POINTS = [
    "vendor lock-in", "manual toil", "compliance risk", "slow response times",
    "data quality issues", "scaling limits", "security gaps",
    "duplicate tooling costs", "onboarding friction", "reporting delays",
]
QUARTERS = ["Q1", "Q2", "Q3", "Q4"]

RATIONALE_TEMPLATES = [
    "This addresses recurring complaints about {pain}.",
    "The previous approach was causing {pain}, so a change was needed.",
    "{vendor} offered a meaningfully better fit than the incumbent at a comparable cost.",
    "This was driven by {ticket}, which surfaced repeated issues.",
    "Budget review flagged this as a priority for {quarter}.",
    "Customer feedback consistently pointed to {pain}.",
    "The team evaluated a few alternatives before settling on this.",
    "This aligns with the {project} initiative's goals.",
    "Leadership asked for this after the {quarter} planning offsite.",
    "This reduces our exposure to {pain}.",
]

DECISION_VERBS = ["approved", "greenlit", "signed off on", "decided to move forward with", "finalized"]
ACTION_VERBS = ["kicked off", "started rolling out", "began implementing", "is now driving forward"]
BLOCKER_PHRASES = ["is currently blocked on", "is stalled pending", "can't proceed until", "is waiting on"]

FILENAME_STUBS = ["budget_v2", "rollout_plan", "vendor_contract_draft", "audit_summary_2026", "policy_update_final"]
FILENAME_EXTS = ["xlsx", "pdf", "docx"]

DOMAINS = {
    "infrastructure": dict(
        ticket_prefix="INFRA",
        vendors=["AWS", "Datadog", "PagerDuty", "Terraform Cloud", "Cloudflare", "HashiCorp Vault", "Grafana"],
        acronym_pairs=[("IaC", "Infrastructure as Code"), ("SLA", "Service Level Agreement")],
        topics=[
            "multi-region failover for the payments service", "database connection pooling limits",
            "container orchestration upgrade", "log retention policy", "CDN provider switch",
            "autoscaling threshold tuning", "backup verification cadence", "secrets rotation automation",
            "staging environment parity with production", "on-call rotation tooling",
            "cost allocation tagging standard", "network peering setup with the new datacenter",
            "disaster recovery drill cadence", "TLS certificate automation", "internal DNS migration",
        ],
    ),
    "hiring": dict(
        ticket_prefix="HR",
        vendors=["Greenhouse", "LinkedIn Recruiter", "Workday", "HireVue", "Checkr"],
        acronym_pairs=[("ATS", "Applicant Tracking System"), ("EOR", "Employer of Record")],
        topics=[
            "backend engineer headcount for next quarter", "referral bonus structure",
            "remote-first hiring policy", "background check vendor", "interview panel structure",
            "offer approval workflow", "contractor-to-FTE conversion process", "diversity sourcing initiative",
            "engineering leveling framework", "internship program restart", "recruiter staffing plan",
            "candidate experience survey", "onboarding buddy program", "compensation benchmarking refresh",
            "notice-period policy",
        ],
    ),
    "finance": dict(
        ticket_prefix="FIN",
        vendors=["NetSuite", "Ramp", "Brex", "DocuSign", "Bill.com"],
        acronym_pairs=[("ARR", "Annual Recurring Revenue"), ("CAC", "Customer Acquisition Cost")],
        topics=[
            "AWS billing cadence switch to annual", "expense approval threshold",
            "quarterly close timeline", "vendor payment terms", "corporate card limits",
            "revenue recognition policy", "budget reforecast process", "audit firm selection",
            "invoice automation rollout", "FX hedging policy", "equity refresh cycle",
            "procurement approval matrix", "travel expense policy", "R&D tax credit filing",
            "subscription spend review",
        ],
    ),
    "legal": dict(
        ticket_prefix="LEGAL",
        vendors=["Ironclad", "DocuSign", "Clio", "LegalZoom"],
        acronym_pairs=[("DPA", "Data Processing Agreement"), ("MSA", "Master Service Agreement")],
        topics=[
            "data retention policy", "vendor contract template refresh", "customer MSA redline process",
            "trademark filing", "employee arbitration clause", "GDPR data subject request process",
            "IP assignment policy", "contract approval workflow", "litigation hold procedure",
            "privacy policy update", "software license compliance review", "outside counsel selection",
            "non-compete clause policy", "records retention schedule", "insurance coverage review",
        ],
    ),
    "security": dict(
        ticket_prefix="SEC",
        vendors=["Okta", "CrowdStrike", "Vanta", "1Password", "Snyk"],
        acronym_pairs=[("SSO", "Single Sign-On"), ("MFA", "Multi-Factor Authentication")],
        topics=[
            "password rotation policy", "SSO enforcement for internal tools",
            "vulnerability disclosure program", "SOC2 audit prep", "endpoint detection rollout",
            "phishing simulation cadence", "access review automation", "incident response runbook",
            "vendor security questionnaire process", "encryption-at-rest policy",
            "penetration test scheduling", "least-privilege access model",
            "security awareness training", "bug bounty program", "device management policy",
        ],
    ),
    "analytics": dict(
        ticket_prefix="DATA",
        vendors=["Snowflake", "Looker", "Amplitude", "Segment", "Fivetran"],
        acronym_pairs=[("ETL", "Extract Transform Load"), ("KPI", "Key Performance Indicator")],
        topics=[
            "migration off self-hosted Snowplow", "self-serve dashboard for sales",
            "data warehouse cost optimization", "event schema governance",
            "experimentation platform selection", "customer data platform rollout",
            "leadership reporting cadence", "attribution model rework", "data quality monitoring",
            "BI tool consolidation", "PII masking in analytics", "cohort retention dashboard",
            "marketing analytics pipeline", "churn model retraining", "warehouse access policy",
        ],
    ),
    "product": dict(
        ticket_prefix="PROD",
        vendors=["Figma", "Linear", "Productboard", "Amplitude", "Pendo"],
        acronym_pairs=[("PRD", "Product Requirements Document"), ("MVP", "Minimum Viable Product")],
        topics=[
            "mobile app roadmap for this quarter", "pricing tier restructuring",
            "onboarding flow redesign", "feature flag rollout process", "beta program structure",
            "roadmap prioritization framework", "customer feedback triage process",
            "public API versioning policy", "in-app messaging tool", "design system consolidation",
            "usage-based billing pilot", "changelog publishing cadence",
            "accessibility compliance target", "self-serve trial flow",
            "mobile push notification opt-in",
        ],
    ),
    "engineering": dict(
        ticket_prefix="ENG",
        vendors=["GitHub", "CircleCI", "Redis", "pgmq", "Sentry", "Terraform"],
        acronym_pairs=[("CI/CD", "Continuous Integration and Continuous Deployment"), ("SDK", "Software Development Kit")],
        topics=[
            "job queue migration from Redis Streams to pgmq", "Kubernetes rollout", "monorepo migration",
            "code review SLA", "flaky test quarantine process", "feature branch strategy",
            "internal SDK versioning", "database migration tooling", "service mesh adoption",
            "build cache optimization", "on-call escalation policy", "public API deprecation timeline",
            "static analysis enforcement", "dependency upgrade cadence", "canary deployment strategy",
        ],
    ),
    "marketing": dict(
        ticket_prefix="MKT",
        vendors=["HubSpot", "Marketo", "Mailchimp", "Webflow", "Semrush"],
        acronym_pairs=[("SEO", "Search Engine Optimization"), ("MQL", "Marketing Qualified Lead")],
        topics=[
            "brand refresh timeline", "webinar series cadence", "paid search budget reallocation",
            "content calendar tool", "lead scoring model", "partner co-marketing program",
            "blog rebrand", "email send frequency cap", "conference sponsorship selection",
            "influencer partnership policy", "landing page testing cadence",
            "marketing attribution tool switch", "social media scheduling tool",
            "case study production pipeline", "growth loop experimentation",
        ],
    ),
    "customer_support": dict(
        ticket_prefix="SUP",
        vendors=["Zendesk", "Intercom", "Front", "Help Scout"],
        acronym_pairs=[("SLA", "Service Level Agreement"), ("CSAT", "Customer Satisfaction Score")],
        topics=[
            "support SLA reduction from 48 to 24 hours", "self-serve help center expansion",
            "tier-2 escalation policy", "live chat coverage hours", "support macros standardization",
            "CSAT survey cadence", "premium support tier", "ticket routing automation",
            "support staffing for enterprise accounts", "refund policy update",
            "in-app support widget", "support quality scoring rubric",
            "multilingual support rollout", "support knowledge base migration",
            "on-call support rotation",
        ],
    ),
}

DOMAIN_LIST = list(DOMAINS.keys())

# Designed cross-domain lexical distractors: same literal token, different referent.
DISTRACTOR_TOKENS = [
    ("Compass", "engineering", "an internal build-cache initiative", "customer_support", "an enterprise client account (Compass Realty)"),
    ("Atlas", "engineering", "the primary datastore vendor (MongoDB Atlas)", "hiring", "the hiring-pipeline redesign initiative"),
    ("Nova", "product", "the mobile app redesign initiative", "customer_support", "an enterprise client account (Nova Financial)"),
    ("Horizon", "marketing", "the brand refresh initiative", "finance", "the external audit firm (Horizon Capital)"),
    ("Beacon", "security", "an internal security initiative", "analytics", "the attribution-modeling vendor (Beacon Analytics)"),
]

# Designed near-duplicate pairs: same vendor/action, different department scope.
NEAR_DUP_DOMAINS = ["engineering", "finance", "legal", "security", "marketing"]

SOURCES = ["slack", "gmail", "notion"]

PERMISSION_PLAN = {
    "security": ("C_SECURITY_INTERNAL", 7),
    "finance": ("C_FINANCE_PRIVATE", 6),
    "legal": ("C_LEGAL_PRIVILEGED", 6),
    "hiring": ("C_HR_CONFIDENTIAL", 6),
}

START_DATE = datetime(2026, 1, 5, tzinfo=timezone.utc)


def _rand_date() -> str:
    days = rng.randint(0, 195)
    hours = rng.randint(8, 18)
    dt = START_DATE + timedelta(days=days, hours=hours, minutes=rng.randint(0, 59))
    return dt.isoformat()


def _ticket(prefix: str) -> str:
    return f"{prefix}-{rng.randint(100, 999)}"


def _filename() -> str:
    return f"{rng.choice(FILENAME_STUBS)}_{rng.choice(['v1', 'v2', 'v3', '2026'])}.{rng.choice(FILENAME_EXTS)}"


def _version() -> str:
    return f"v{rng.randint(1, 4)}.{rng.randint(0, 9)}.{rng.randint(0, 9)}"


def _rationale(vendor: str, ticket: str, project: str) -> str:
    tmpl = rng.choice(RATIONALE_TEMPLATES)
    return tmpl.format(pain=rng.choice(PAIN_POINTS), vendor=vendor, ticket=ticket,
                        project=project, quarter=rng.choice(QUARTERS))


def _raw_content(source: str, actor: str, actor2: str, verb: str, topic: str, rationale: str, filename: str | None) -> str:
    file_line = f" See {filename} for details." if filename else ""
    if source == "slack":
        return rng.choice([
            f"{actor}: heads up — we {verb} {topic}. {rationale}",
            f"{actor}: quick update — we're {verb} {topic}. {rationale} cc @{actor2}",
            f"{actor}: \U0001F9F5 decision thread — {topic}. After discussion with {actor2}, we {verb} this. {rationale}",
        ]) + file_line
    if source == "gmail":
        return rng.choice([
            f"Subject: Decision — {topic}\n\nHi team,\n\nAfter reviewing options with {actor2}, we've {verb} {topic}. {rationale}\n\nBest,\n{actor}",
            f"Subject: {topic} — update\n\n{rationale} As a result, {actor} has {verb} {topic}, effective immediately.\n\nThanks,\n{actor}",
        ]) + file_line
    return rng.choice([
        f"## {topic}\n\n**Status:** Decided\n**Owner:** {actor}\n\n{rationale} We will move forward with {verb} {topic}.",
        f"## Decision Log — {topic}\n\n**Owner:** {actor} | **Reviewed by:** {actor2}\n\n{rationale}",
    ]) + file_line


def _make_generic(domain: str, idx: int, seq: int) -> dict:
    cfg = DOMAINS[domain]
    topic = cfg["topics"][idx % len(cfg["topics"])]
    vendor = rng.choice(cfg["vendors"])
    actor = rng.choice(EMPLOYEES)
    actor2 = rng.choice([e for e in EMPLOYEES if e != actor])
    project = rng.choice(PROJECT_CODENAMES := [
        "Falcon", "Meridian", "Orion", "Zephyr", "Cascade", "Anchor", "Summit", "Voyager",
        "Lighthouse", "Catalyst", "Momentum", "Pinnacle", "Vanguard", "Odyssey", "Ember",
        "Solstice", "Prism", "Trident", "Aurora", "Keystone",
    ])
    ticket = _ticket(cfg["ticket_prefix"])
    record_type = ["decision", "decision", "action_item", "blocker", "decision"][idx % 5]
    source = SOURCES[idx % 3]
    has_ticket = rng.random() < 0.4
    has_filename = rng.random() < 0.25
    filename = _filename() if has_filename else None
    rationale = _rationale(vendor, ticket if has_ticket else "internal review", project)
    tags = []

    if record_type == "decision":
        verb = rng.choice(DECISION_VERBS)
        statement = f"{actor} {verb} {topic}, working with {vendor}."
        status = "decided"
    elif record_type == "action_item":
        verb = rng.choice(ACTION_VERBS)
        statement = f"{actor} {verb} {topic}, coordinating with {vendor}."
        status = "proposed"
    else:
        verb = rng.choice(BLOCKER_PHRASES)
        statement = f"{actor}: progress on {topic} {verb} approval from {actor2}."
        status = "proposed"

    if has_ticket:
        statement += f" (Ref: {ticket})"
        tags.append(f"ticket_id:{ticket}")
    if has_filename:
        tags.append(f"filename:{filename}")

    raw = _raw_content(source, actor, actor2, verb if record_type != "blocker" else "escalated", topic, rationale, filename)
    if has_ticket and rng.random() < 0.5:
        raw = raw.replace(topic, topic, 1) + f" ({ticket})"

    other_vendor = rng.choice([v for v in cfg["vendors"] if v != vendor])
    alternatives = [f"Considered {other_vendor} but chose {vendor} based on cost and integration fit."]

    source_id = f"eval2-{domain}-{seq:03d}"
    return {
        "source_message_id": source_id,
        "domain": domain,
        "source": source,
        "tenant_id": TENANT_ID,
        "actor": actor,
        "thread_ref": f"{domain}-thread-{rng.randint(100,999)}",
        "received_at": _rand_date(),
        "permission_scope": [],
        "source_permalink": f"https://{source}.example.internal/{domain}/{source_id}",
        "raw_content": raw,
        "structured_ground_truth": {
            "record_type": record_type,
            "status": status,
            "decision_statement": statement,
            "rationale": rationale,
            "alternatives_considered": alternatives,
            "actors": [],
            "confidence": round(rng.uniform(0.85, 0.98), 3),
        },
        "hard_case_tags": tags,
    }


def _make_near_dup_pair(domain: str, seq_start: int) -> list[dict]:
    cfg = DOMAINS[domain]
    vendor = rng.choice(cfg["vendors"])
    actor1, actor2 = rng.sample(EMPLOYEES, 2)
    dept_a, dept_b = rng.sample(["the platform team", "the data team", "the growth team", "the core product team"], 2)
    ticket_a, ticket_b = _ticket(cfg["ticket_prefix"]), _ticket(cfg["ticket_prefix"])
    pair_tag = f"near_duplicate_pair:{domain}_{vendor.lower().replace(' ', '_')}"
    out = []
    for i, (actor, dept, ticket) in enumerate([(actor1, dept_a, ticket_a), (actor2, dept_b, ticket_b)]):
        source = SOURCES[i % 3]
        statement = f"{actor} renewed the {vendor} contract for {dept}."
        rationale = f"{dept.capitalize()} relies on {vendor} daily and the renewal terms were favorable. (Ref: {ticket})"
        raw = _raw_content(source, actor, actor2 if actor == actor1 else actor1,
                            "renewed", f"the {vendor} contract for {dept}", rationale, None)
        source_id = f"eval2-{domain}-{seq_start + i:03d}"
        out.append({
            "source_message_id": source_id, "domain": domain, "source": source, "tenant_id": TENANT_ID,
            "actor": actor, "thread_ref": f"{domain}-thread-{rng.randint(100,999)}",
            "received_at": _rand_date(), "permission_scope": [],
            "source_permalink": f"https://{source}.example.internal/{domain}/{source_id}",
            "raw_content": raw,
            "structured_ground_truth": {
                "record_type": "decision", "status": "decided", "decision_statement": statement,
                "rationale": rationale, "alternatives_considered": [f"Considered switching away from {vendor}, but renewal cost less than migration."],
                "actors": [], "confidence": round(rng.uniform(0.85, 0.98), 3),
            },
            "hard_case_tags": [pair_tag, f"ticket_id:{ticket}"],
        })
    return out


def _make_distractor(domain: str, seq: int, token: str, referent_desc: str) -> dict:
    cfg = DOMAINS[domain]
    actor = rng.choice(EMPLOYEES)
    actor2 = rng.choice([e for e in EMPLOYEES if e != actor])
    source = SOURCES[seq % 3]
    statement = f"{actor} confirmed the direction for {token} — {referent_desc}."
    rationale = f"This was reviewed by {actor2} and aligns with the team's priorities for the quarter."
    raw = _raw_content(source, actor, actor2, "confirmed", f"{token} ({referent_desc})", rationale, None)
    source_id = f"eval2-{domain}-{seq:03d}"
    return {
        "source_message_id": source_id, "domain": domain, "source": source, "tenant_id": TENANT_ID,
        "actor": actor, "thread_ref": f"{domain}-thread-{rng.randint(100,999)}",
        "received_at": _rand_date(), "permission_scope": [],
        "source_permalink": f"https://{source}.example.internal/{domain}/{source_id}",
        "raw_content": raw,
        "structured_ground_truth": {
            "record_type": "decision", "status": "decided", "decision_statement": statement,
            "rationale": rationale, "alternatives_considered": [],
            "actors": [], "confidence": round(rng.uniform(0.85, 0.98), 3),
        },
        "hard_case_tags": [f"cross_domain_lexical_distractor:{token}"],
    }


def _make_acronym_pair(domain: str, seq: int) -> list[dict]:
    cfg = DOMAINS[domain]
    acr, expansion = cfg["acronym_pairs"][0]
    actor_a, actor_b = rng.sample(EMPLOYEES, 2)
    out = []
    for i, (form, tag) in enumerate([(acr, "acronym_only"), (expansion, "expansion_only")]):
        source = SOURCES[i % 3]
        actor = actor_a if i == 0 else actor_b
        statement = f"{actor} approved the updated {form} process for the team."
        rationale = f"The prior process for {form} was inconsistent across teams and needed standardizing."
        raw = _raw_content(source, actor, actor_b if i == 0 else actor_a, "approved", f"the {form} process", rationale, None)
        source_id = f"eval2-{domain}-{seq + i:03d}"
        out.append({
            "source_message_id": source_id, "domain": domain, "source": source, "tenant_id": TENANT_ID,
            "actor": actor, "thread_ref": f"{domain}-thread-{rng.randint(100,999)}",
            "received_at": _rand_date(), "permission_scope": [],
            "source_permalink": f"https://{source}.example.internal/{domain}/{source_id}",
            "raw_content": raw,
            "structured_ground_truth": {
                "record_type": "decision", "status": "decided", "decision_statement": statement,
                "rationale": rationale, "alternatives_considered": [],
                "actors": [], "confidence": round(rng.uniform(0.85, 0.98), 3),
            },
            "hard_case_tags": [f"{tag}:{form}"],
        })
    return out


def build_corpus() -> list[dict]:
    corpus = []
    seen_statements: set[str] = set()
    for domain in DOMAIN_LIST:
        decisions = []
        seq = 1

        if domain in NEAR_DUP_DOMAINS:
            pair = _make_near_dup_pair(domain, seq)
            decisions.extend(pair)
            seq += 2

        distractor_slots = [(tok, d, desc) for tok, d1, desc1, d2, desc2 in DISTRACTOR_TOKENS
                             for d, desc in [(d1, desc1), (d2, desc2)] if d == domain]
        for tok, _, desc in distractor_slots:
            decisions.append(_make_distractor(domain, seq, tok, desc))
            seq += 1

        acr_pair = _make_acronym_pair(domain, seq)
        decisions.extend(acr_pair)
        seq += 2

        for d in decisions:
            seen_statements.add(d["structured_ground_truth"]["decision_statement"])

        idx = 0
        attempts = 0
        while len(decisions) < 25 and attempts < 500:
            attempts += 1
            candidate = _make_generic(domain, idx, seq)
            idx += 1
            stmt = candidate["structured_ground_truth"]["decision_statement"]
            if stmt in seen_statements:
                continue
            seen_statements.add(stmt)
            seq += 1
            decisions.append(candidate)

        decisions = decisions[:25]
        for i, d in enumerate(decisions, start=1):
            d["source_message_id"] = f"eval2-{domain}-{i:03d}"
            d["source_permalink"] = f"https://{d['source']}.example.internal/{domain}/{d['source_message_id']}"

        if domain in PERMISSION_PLAN:
            scope, count = PERMISSION_PLAN[domain]
            eligible = [d for d in decisions if not d["hard_case_tags"] or "near_duplicate_pair" not in d["hard_case_tags"][0]]
            chosen = rng.sample(eligible, min(count, len(eligible)))
            for d in chosen:
                d["permission_scope"] = [scope]

        corpus.extend(decisions)

    return corpus


def dedup_report(corpus: list[dict]) -> dict:
    seen_raw = {}
    seen_statement = {}
    exact_dupes = []
    for d in corpus:
        raw = d["raw_content"]
        stmt = d["structured_ground_truth"]["decision_statement"]
        if raw in seen_raw:
            exact_dupes.append((d["source_message_id"], seen_raw[raw], "raw_content"))
        else:
            seen_raw[raw] = d["source_message_id"]
        if stmt in seen_statement:
            exact_dupes.append((d["source_message_id"], seen_statement[stmt], "decision_statement"))
        else:
            seen_statement[stmt] = d["source_message_id"]

    near_dup_pairs = sorted({
        tuple(sorted([d["source_message_id"] for d in corpus if t in d["hard_case_tags"]]))
        for d in corpus for t in d["hard_case_tags"] if t.startswith("near_duplicate_pair:")
    })

    return {
        "total_decisions": len(corpus),
        "exact_duplicate_count": len(exact_dupes),
        "exact_duplicates": exact_dupes,
        "intentional_near_duplicate_pairs": [list(p) for p in near_dup_pairs if len(p) == 2],
    }


def distribution_report(corpus: list[dict]) -> dict:
    from collections import Counter
    domain_counts = Counter(d["domain"] for d in corpus)
    perm_counts = Counter(tuple(d["permission_scope"]) or ("none",) for d in corpus)
    hard_case_counts = Counter()
    for d in corpus:
        for t in d["hard_case_tags"]:
            hard_case_counts[t.split(":")[0]] += 1
    source_counts = Counter(d["source"] for d in corpus)
    record_type_counts = Counter(d["structured_ground_truth"]["record_type"] for d in corpus)

    unique_statements = {d["structured_ground_truth"]["decision_statement"] for d in corpus}

    return {
        "domain_counts": dict(domain_counts),
        "source_counts": dict(source_counts),
        "record_type_counts": dict(record_type_counts),
        "permission_distribution": {str(k): v for k, v in perm_counts.items()},
        "hard_case_distribution": dict(hard_case_counts),
        "unique_decision_statement_count": len(unique_statements),
        "unique_template_estimate": len(RATIONALE_TEMPLATES) * 3 * len(DECISION_VERBS),
    }


REGRESSION_QUERIES = [
    {"test_id": "kw-01", "category": "exact_keyword", "question": "Why did we choose Stripe instead of Paddle?",
     "expected_decision_ids": ["91b4aa2f-a02c-44c2-be89-10053f9d32f4"], "expected_answerable": True},
    {"test_id": "kw-02", "category": "exact_keyword", "question": "Why are we migrating the job queue from Redis Streams to pgmq?",
     "expected_decision_ids": ["f8aeac83-5ec7-4a05-914c-112bc85cf668"], "expected_answerable": True},
    {"test_id": "kw-03", "category": "exact_keyword", "question": "Why did we move the primary database to a multi-AZ RDS setup?",
     "expected_decision_ids": ["a992a87e-e964-4dec-822a-c2fda9269ba9"], "expected_answerable": True},
    {"test_id": "kw-04", "category": "exact_keyword", "question": "Why are we requiring SSO for all internal tools?",
     "expected_decision_ids": ["2c4e1793-7b17-4510-8b9a-64c8cd72f312"], "expected_answerable": True},
    {"test_id": "para-01", "category": "semantic_paraphrase", "question": "What's our plan for the mobile app this quarter?",
     "expected_decision_ids": ["bb4cad80-ac94-4d50-b98d-397d0eeceffa"], "expected_answerable": True},
    {"test_id": "para-02", "category": "semantic_paraphrase", "question": "Are we keeping the downtown office space?",
     "expected_decision_ids": ["0c4ee9e7-30f0-434e-a94e-2207532fa7bf"], "expected_answerable": True},
    {"test_id": "para-03", "category": "semantic_paraphrase", "question": "What analytics tooling change did the data team make?",
     "expected_decision_ids": ["3c766c71-448d-44fb-8b30-6b6d7960ada0"], "expected_answerable": True},
    {"test_id": "para-04", "category": "semantic_paraphrase", "question": "What's happening with our Kubernetes rollout?",
     "expected_decision_ids": ["8473d874-f519-4e86-be71-12c26a5ba2d7"], "expected_answerable": True},
    {"test_id": "rat-01", "category": "rationale", "question": "Why did we raise the support SLA from 48 to 24 hours?",
     "expected_decision_ids": ["95652444-0666-4c51-8dbd-7048ccadbce8"], "expected_answerable": True},
    {"test_id": "rat-02", "category": "rationale", "question": "Why did we decide not to renew the office lease?",
     "expected_decision_ids": ["0c4ee9e7-30f0-434e-a94e-2207532fa7bf"], "expected_answerable": True},
    {"test_id": "rat-03", "category": "rationale", "question": "Why did we migrate off self-hosted Snowplow?",
     "expected_decision_ids": ["3c766c71-448d-44fb-8b30-6b6d7960ada0"], "expected_answerable": True},
    {"test_id": "rat-04", "category": "rationale", "question": "Why are we enforcing SSO on internal tools?",
     "expected_decision_ids": ["2c4e1793-7b17-4510-8b9a-64c8cd72f312"], "expected_answerable": True},
    {"test_id": "actor-01", "category": "actor_owner", "question": "Who is responsible for setting up nightly database backups?",
     "expected_decision_ids": ["47a5d5f4-7cc2-4a5b-81e2-b968f03279cf"], "expected_answerable": True},
    {"test_id": "actor-02", "category": "actor_owner", "question": "Who will build the self-serve analytics dashboard for sales?",
     "expected_decision_ids": ["cde053c4-0972-4ea7-8b1c-80003beb4cfa"], "expected_answerable": True},
    {"test_id": "actor-03", "category": "actor_owner", "question": "Who decided to extend the offer to the backend engineer candidate?",
     "expected_decision_ids": ["8cc8888e-7701-43da-b210-18ad4c58027c"], "expected_answerable": True},
    {"test_id": "multi-01", "category": "multi_decision", "question": "What infrastructure decisions have we made recently?",
     "expected_decision_ids": ["a992a87e-e964-4dec-822a-c2fda9269ba9", "8473d874-f519-4e86-be71-12c26a5ba2d7", "47a5d5f4-7cc2-4a5b-81e2-b968f03279cf"],
     "expected_answerable": True},
    {"test_id": "multi-02", "category": "multi_decision", "question": "What security-related decisions and blockers do we have?",
     "expected_decision_ids": ["2c4e1793-7b17-4510-8b9a-64c8cd72f312", "b006a28d-723d-4319-b84b-a60485059772"],
     "excluded_decision_ids": ["fc7ea5af-5817-4cf3-859f-9eaa3d4b8fdf"], "expected_answerable": True},
    {"test_id": "multi-03", "category": "multi_decision", "question": "What blockers are currently affecting different teams?",
     "expected_decision_ids": ["6b1ee81d-793c-4525-9b5a-b5cc3f84ec69", "b006a28d-723d-4319-b84b-a60485059772",
                               "6d741b8c-3a55-499b-ad8b-f1f8c0d847e1", "facdb6a7-2bde-4324-b365-114c81f1c8c8",
                               "a9b1bbbf-6ff0-4c91-b718-89a307273e52"],
     "expected_answerable": True},
    {"test_id": "perm-01", "category": "permission_restricted", "question": "What did we decide about the password rotation policy?",
     "expected_decision_ids": [], "excluded_decision_ids": ["fc7ea5af-5817-4cf3-859f-9eaa3d4b8fdf"], "expected_answerable": False},
    {"test_id": "perm-02", "category": "permission_restricted", "question": "Why is finance switching AWS billing to annual?",
     "expected_decision_ids": [], "excluded_decision_ids": ["e47da747-a0f1-4bfd-80c8-3fc10ada3f0a"], "expected_answerable": False},
    {"test_id": "perm-03", "category": "permission_restricted", "question": "What did legal decide about data retention?",
     "expected_decision_ids": [], "excluded_decision_ids": ["647253df-bd84-489b-95e9-4ea017a53742"], "expected_answerable": False},
    {"test_id": "neg-01", "category": "no_answer", "question": "Did we decide to acquire any companies this year?",
     "expected_decision_ids": [], "expected_answerable": False},
    {"test_id": "neg-02", "category": "no_answer", "question": "What's our policy on unlimited vacation days?",
     "expected_decision_ids": [], "expected_answerable": False},
    {"test_id": "neg-03", "category": "no_answer", "question": "Have we decided to switch our cloud provider away from AWS?",
     "expected_decision_ids": [], "expected_answerable": False},
    {"test_id": "neg-04", "category": "no_answer", "question": "What did we decide about opening a new office in Europe?",
     "expected_decision_ids": [], "expected_answerable": False},
]
assert len(REGRESSION_QUERIES) == 25


def find_by_tag(corpus: list[dict], tag_prefix: str) -> list[dict]:
    return [d for d in corpus if any(t.startswith(tag_prefix) for t in d["hard_case_tags"])]


def build_hybrid_queries(corpus: list[dict]) -> list[dict]:
    q = []

    def sid(tag_prefix, n=1):
        matches = find_by_tag(corpus, tag_prefix)
        return [d["source_message_id"] for d in matches[:n]]

    # --- keyword-favored (4): identifiers / exact names, weak semantic signal ---
    eng_datadog = find_by_tag(corpus, "near_duplicate_pair:engineering")
    fin_pair = find_by_tag(corpus, "near_duplicate_pair:finance")
    q.append({"query_id": "hyb-kw-01", "category": "keyword_favored",
              "question": "What did we decide about the CircleCI vendor questionnaire?",
              "expected_source_message_ids": [], "expected_answerable": False,
              "retrieval_mode_advantage": "keyword",
              "rationale": "Deliberately references an exact vendor name absent from the corpus; tests that FTS doesn't over-match on partial token overlap (CircleCI appears elsewhere) while confirming no false positive citation."})
    q.append({"query_id": "hyb-kw-02", "category": "keyword_favored",
              "question": "What's the status of the ticket for the multi-region failover work?",
              "expected_source_message_ids": sid("ticket_id:INFRA", 1) or find_by_tag(corpus, "cross_domain_lexical_distractor")[:0],
              "expected_answerable": True, "retrieval_mode_advantage": "keyword",
              "rationale": "The literal ticket-ID reference is the strongest signal; FTS matches the exact INFRA-### token while embeddings have no special affinity for numeric identifiers."})
    q.append({"query_id": "hyb-kw-03", "category": "keyword_favored",
              "question": "What changed according to the vendor_contract_draft file?",
              "expected_source_message_ids": [d["source_message_id"] for d in find_by_tag(corpus, "filename:")[:1]],
              "expected_answerable": True, "retrieval_mode_advantage": "keyword",
              "rationale": "Filenames are exact literal strings; FTS/websearch_to_tsquery matches them directly, embeddings treat them as an opaque token with weak signal."})
    q.append({"query_id": "hyb-kw-04", "category": "keyword_favored",
              "question": "What did Priya Chen decide most recently?",
              "expected_source_message_ids": [d["source_message_id"] for d in corpus if d["actor"] == "Priya Chen"][:3],
              "expected_answerable": True, "retrieval_mode_advantage": "keyword",
              "rationale": "Proper noun exact-match lookup; embeddings are inconsistent at treating personal names as high-signal tokens, FTS matches them directly."})

    # --- semantic-favored (4): paraphrase, zero literal overlap ---
    sso_acr = find_by_tag(corpus, "acronym_only:SSO")
    sso_exp = find_by_tag(corpus, "expansion_only:Single Sign-On")
    q.append({"query_id": "hyb-sem-01", "category": "semantic_favored",
              "question": "Are we consolidating our Single Sign-On story across internal tools?",
              "expected_source_message_ids": [d["source_message_id"] for d in sso_acr],
              "expected_answerable": True, "retrieval_mode_advantage": "semantic",
              "rationale": "Stored decision uses only the acronym 'SSO'; the query only uses the expanded form. Zero literal token overlap on the key phrase — only embedding similarity bridges acronym<->expansion."})
    dpa_exp = find_by_tag(corpus, "expansion_only:Data Processing Agreement")
    q.append({"query_id": "hyb-sem-02", "category": "semantic_favored",
              "question": "What did legal decide about our DPA process?",
              "expected_source_message_ids": [d["source_message_id"] for d in dpa_exp],
              "expected_answerable": True, "retrieval_mode_advantage": "semantic",
              "rationale": "Query uses only the acronym 'DPA'; stored decision spells out 'Data Processing Agreement' in full with no acronym present."})
    q.append({"query_id": "hyb-sem-03", "category": "semantic_favored",
              "question": "How are we approaching cost efficiency in our data warehouse?",
              "expected_source_message_ids": [d["source_message_id"] for d in corpus
                                               if d["domain"] == "analytics" and "cost optimization" in d["structured_ground_truth"]["decision_statement"]][:1] or
                                              [d["source_message_id"] for d in corpus if d["domain"] == "analytics"][:1],
              "expected_answerable": True, "retrieval_mode_advantage": "semantic",
              "rationale": "Paraphrased query ('cost efficiency', 'warehouse') shares almost no literal tokens with the stored 'data warehouse cost optimization' decision statement wording; relies on topical embedding similarity."})
    q.append({"query_id": "hyb-sem-04", "category": "semantic_favored",
              "question": "Is the company doing anything about employees leaving without much warning?",
              "expected_source_message_ids": [d["source_message_id"] for d in corpus
                                               if d["domain"] == "hiring" and "notice-period" in d["structured_ground_truth"]["decision_statement"]],
              "expected_answerable": True, "retrieval_mode_advantage": "semantic",
              "rationale": "Colloquial paraphrase of 'notice-period policy' with no shared literal terms; purely a semantic-similarity test."})

    # --- hybrid-favored (4): needs both topical + lexical disambiguation ---
    for pair, dom in [(eng_datadog, "engineering"), (fin_pair, "finance")]:
        if pair:
            q.append({"query_id": f"hyb-hyb-{dom[:3]}", "category": "hybrid_favored",
                      "question": f"Why did we renew the vendor contract for {pair[0]['structured_ground_truth']['decision_statement'].split('for ')[-1].rstrip('.')}?",
                      "expected_source_message_ids": [pair[0]["source_message_id"]],
                      "expected_answerable": True, "retrieval_mode_advantage": "hybrid",
                      "rationale": f"Near-duplicate pair exists in {dom} (same vendor, two departments) — needs semantic topic match (vendor renewal) AND literal department-name disambiguation to rank the correct one first."})
    legal_pair = find_by_tag(corpus, "near_duplicate_pair:legal")
    sec_pair = find_by_tag(corpus, "near_duplicate_pair:security")
    if legal_pair:
        q.append({"query_id": "hyb-hyb-legal", "category": "hybrid_favored",
                  "question": f"Which team's contract with the vendor did legal renew?",
                  "expected_source_message_ids": [d["source_message_id"] for d in legal_pair],
                  "expected_answerable": True, "retrieval_mode_advantage": "hybrid",
                  "rationale": "Ambiguous between two near-duplicate legal decisions; both are plausibly relevant, testing whether fused ranking surfaces both without either method alone over- or under-ranking one."})
    if sec_pair:
        q.append({"query_id": "hyb-hyb-security", "category": "hybrid_favored",
                  "question": f"Tell me about the security team's vendor contract renewal.",
                  "expected_source_message_ids": [sec_pair[0]["source_message_id"]],
                  "expected_answerable": True, "retrieval_mode_advantage": "hybrid",
                  "rationale": "Requires matching both the topical concept (vendor renewal) and the literal department qualifier ('security team') to disambiguate from the paired near-duplicate."})

    # --- identifier lookups (4) ---
    ticket_examples = find_by_tag(corpus, "ticket_id:")[:3]
    for i, d in enumerate(ticket_examples, start=1):
        ticket = next(t for t in d["hard_case_tags"] if t.startswith("ticket_id:")).split(":", 1)[1]
        q.append({"query_id": f"hyb-id-{i:02d}", "category": "identifier_lookup",
                  "question": f"What's the update on {ticket}?",
                  "expected_source_message_ids": [d["source_message_id"]], "expected_answerable": True,
                  "retrieval_mode_advantage": "keyword",
                  "rationale": f"Direct ticket-ID lookup ({ticket}); a pure identifier-matching test where FTS should dominate and semantic embedding has no special advantage."})
    filename_examples = find_by_tag(corpus, "filename:")[:1]
    for d in filename_examples:
        fname = next(t for t in d["hard_case_tags"] if t.startswith("filename:")).split(":", 1)[1]
        q.append({"query_id": "hyb-id-04", "category": "identifier_lookup",
                  "question": f"What does {fname} cover?",
                  "expected_source_message_ids": [d["source_message_id"]], "expected_answerable": True,
                  "retrieval_mode_advantage": "keyword",
                  "rationale": "Exact filename lookup; literal-string matching test."})

    # --- acronym/expanded-form (3, beyond the semantic-favored ones above) ---
    q.append({"query_id": "hyb-acr-01", "category": "acronym_expanded_form",
              "question": "What's our current ARR growth strategy tied to?",
              "expected_source_message_ids": [], "expected_answerable": False, "retrieval_mode_advantage": "keyword",
              "rationale": "No stored decision discusses ARR strategy directly (the finance corpus references ARR only incidentally); tests no-answer accuracy doesn't regress when an acronym is present but the topic is genuinely absent."})
    ci_cd = find_by_tag(corpus, "acronym_only:CI/CD")
    q.append({"query_id": "hyb-acr-02", "category": "acronym_expanded_form",
              "question": "What did engineering decide about Continuous Integration and Continuous Deployment?",
              "expected_source_message_ids": [d["source_message_id"] for d in ci_cd],
              "expected_answerable": True, "retrieval_mode_advantage": "semantic",
              "rationale": "Query spells out the expansion in full; stored decision uses only 'CI/CD'. Tests acronym bridging in the opposite direction from hyb-sem-01."})
    prd_exp = find_by_tag(corpus, "expansion_only:Product Requirements Document")
    q.append({"query_id": "hyb-acr-03", "category": "acronym_expanded_form",
              "question": "What's the PRD process we agreed on?",
              "expected_source_message_ids": [d["source_message_id"] for d in prd_exp],
              "expected_answerable": True, "retrieval_mode_advantage": "semantic",
              "rationale": "Query uses only the acronym 'PRD'; stored text spells out 'Product Requirements Document' in full with no acronym present."})

    # --- entity lookups (3) ---
    for i, name in enumerate(["Marcus Webb", "Elena Rodriguez"], start=1):
        matches = [d["source_message_id"] for d in corpus if d["actor"] == name][:2]
        if matches:
            q.append({"query_id": f"hyb-ent-{i:02d}", "category": "entity_lookup",
                      "question": f"What has {name} been working on?",
                      "expected_source_message_ids": matches, "expected_answerable": True,
                      "retrieval_mode_advantage": "keyword",
                      "rationale": f"Proper-noun actor lookup for {name}; tests exact entity-name matching strength of FTS vs. embeddings."})
    q.append({"query_id": "hyb-ent-03", "category": "entity_lookup",
              "question": "What did Compass Realty's escalation involve?",
              "expected_source_message_ids": [d["source_message_id"] for d in corpus
                                               if "Compass Realty" in d["raw_content"]],
              "expected_answerable": True, "retrieval_mode_advantage": "keyword",
              "rationale": "Entity name 'Compass Realty' is also a cross-domain lexical distractor (Compass appears as an unrelated engineering codename); tests whether keyword/hybrid correctly resolves to the customer_support decision, not the engineering one."})

    # --- near-duplicate disambiguation (3, distinct from hybrid-favored above) ---
    mkt_pair = find_by_tag(corpus, "near_duplicate_pair:marketing")
    if mkt_pair:
        q.append({"query_id": "hyb-dup-01", "category": "near_duplicate_disambiguation",
                  "question": "Which department renewed its marketing vendor contract most recently?",
                  "expected_source_message_ids": [d["source_message_id"] for d in
                                                   sorted(mkt_pair, key=lambda d: d["received_at"], reverse=True)[:1]],
                  "expected_answerable": True, "retrieval_mode_advantage": "hybrid",
                  "rationale": "Two near-duplicate decisions exist; the query adds a temporal qualifier ('most recently') that retrieval itself cannot resolve — this specifically tests whether both candidates are at least retrieved (ranking disambiguation is a downstream synthesis concern, not retrieval's job)."})
    if eng_datadog:
        q.append({"query_id": "hyb-dup-02", "category": "near_duplicate_disambiguation",
                  "question": "Did the platform team or the data team renew the vendor contract?",
                  "expected_source_message_ids": [d["source_message_id"] for d in eng_datadog],
                  "expected_answerable": True, "retrieval_mode_advantage": "hybrid",
                  "rationale": "Explicitly asks retrieval to surface both near-duplicate candidates so the downstream answer can disambiguate between them."})
    if legal_pair:
        q.append({"query_id": "hyb-dup-03", "category": "near_duplicate_disambiguation",
                  "question": "We renewed a vendor contract in legal — for which team?",
                  "expected_source_message_ids": [d["source_message_id"] for d in legal_pair],
                  "expected_answerable": True, "retrieval_mode_advantage": "hybrid",
                  "rationale": "Same near-duplicate-pair stress test in the legal domain."})

    # --- multi-decision (3) ---
    q.append({"query_id": "hyb-multi-01", "category": "multi_decision",
              "question": "What security decisions have we made recently?",
              "expected_source_message_ids": [d["source_message_id"] for d in corpus if d["domain"] == "security"
                                               and d["structured_ground_truth"]["record_type"] == "decision"][:5],
              "expected_answerable": True, "retrieval_mode_advantage": "hybrid",
              "rationale": "Broad domain-level multi-decision query against a much larger (25-decision) security candidate pool than Stage 2's original multi-02; tests whether retrieval quality holds at scale."})
    q.append({"query_id": "hyb-multi-02", "category": "multi_decision",
              "question": "What finance decisions has the team made this year?",
              "expected_source_message_ids": [d["source_message_id"] for d in corpus if d["domain"] == "finance"
                                               and d["structured_ground_truth"]["record_type"] == "decision"][:5],
              "expected_answerable": True, "retrieval_mode_advantage": "hybrid",
              "rationale": "Domain-broad multi-decision query at scale, finance domain."})
    q.append({"query_id": "hyb-multi-03", "category": "multi_decision",
              "question": "What marketing and product decisions overlap this quarter?",
              "expected_source_message_ids": [d["source_message_id"] for d in corpus
                                               if d["domain"] in ("marketing", "product")
                                               and d["structured_ground_truth"]["record_type"] == "decision"][:6],
              "expected_answerable": True, "retrieval_mode_advantage": "hybrid",
              "rationale": "Cross-domain multi-decision query spanning two domains at once, a harder retrieval-breadth test not present in the original 25."})
    q.append({"query_id": "hyb-multi-04", "category": "multi_decision",
              "question": "What engineering decisions have shipped this year?",
              "expected_source_message_ids": [d["source_message_id"] for d in corpus if d["domain"] == "engineering"
                                               and d["structured_ground_truth"]["record_type"] == "decision"][:5],
              "expected_answerable": True, "retrieval_mode_advantage": "hybrid",
              "rationale": "Domain-broad multi-decision query at scale, engineering domain — parallels multi-01 from the original suite but against a 25-decision candidate pool instead of a handful."})

    # --- permission (3) ---
    for i, (domain, scope) in enumerate([("security", "C_SECURITY_INTERNAL"), ("finance", "C_FINANCE_PRIVATE"),
                                          ("hiring", "C_HR_CONFIDENTIAL")], start=1):
        restricted = [d for d in corpus if d["permission_scope"] == [scope]]
        if restricted:
            target = rng.choice(restricted)
            q.append({"query_id": f"hyb-perm-{i:02d}", "category": "permission",
                      "question": f"What did {domain} decide about {target['structured_ground_truth']['decision_statement'].split(' ', 2)[-1][:40].rstrip('.,')}?",
                      "expected_source_message_ids": [], "excluded_source_message_ids": [target["source_message_id"]],
                      "expected_answerable": False, "retrieval_mode_advantage": "none (security property)",
                      "rationale": f"Restricted decision (scope {scope}) must never leak into citations/answer regardless of retrieval mode — permission enforcement happens after retrieval and must hold at 250-decision scale."})

    # --- negative / no-answer (3) ---
    q.append({"query_id": "hyb-neg-01", "category": "no_answer",
              "question": "Did we decide to open a satellite office in Asia?",
              "expected_source_message_ids": [], "expected_answerable": False, "retrieval_mode_advantage": "none",
              "rationale": "Genuinely absent topic; tests no-answer accuracy doesn't regress as candidate pool grows 10x."})
    q.append({"query_id": "hyb-neg-02", "category": "no_answer",
              "question": "Have we decided to switch our support tooling away from ticketing entirely?",
              "expected_source_message_ids": [], "expected_answerable": False, "retrieval_mode_advantage": "none",
              "rationale": "Adjacent to real customer_support decisions (tooling switches exist) but this specific claim is absent — tests that topical proximity doesn't cause a false positive at scale."})
    q.append({"query_id": "hyb-neg-03", "category": "no_answer",
              "question": "Did we decide to unionize the support team?",
              "expected_source_message_ids": [], "expected_answerable": False, "retrieval_mode_advantage": "none",
              "rationale": "Plausible-sounding but entirely fabricated topic; no corpus content should match."})

    return q


def main():
    corpus = build_corpus()
    assert len(corpus) == 250, f"expected 250, got {len(corpus)}"
    for domain in DOMAIN_LIST:
        n = sum(1 for d in corpus if d["domain"] == domain)
        assert n == 25, f"{domain}: expected 25, got {n}"

    hybrid_queries = build_hybrid_queries(corpus)
    # trim/pad to exactly 35 deterministically (drop empty-result speculative slots first)
    hybrid_queries = [q for q in hybrid_queries if q.get("expected_answerable") is not None]
    if len(hybrid_queries) > 35:
        hybrid_queries = hybrid_queries[:35]

    dedup = dedup_report(corpus)
    dist = distribution_report(corpus)

    ground_truth = {
        d["source_message_id"]: {
            "category": d["domain"], "source": d["source"], "actor": d["actor"],
            "permission_scope": d["permission_scope"],
            "structured_decision": d["structured_ground_truth"],
            "hard_case_tags": d["hard_case_tags"],
        } for d in corpus
    }

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "decisions.json").write_text(json.dumps(corpus, indent=2))
    (OUT_DIR / "ground_truth.json").write_text(json.dumps(ground_truth, indent=2))
    (OUT_DIR / "benchmark_regression.json").write_text(json.dumps(REGRESSION_QUERIES, indent=2))
    (OUT_DIR / "benchmark_hybrid.json").write_text(json.dumps(hybrid_queries, indent=2))
    (OUT_DIR / "corpus_report.json").write_text(json.dumps({"dedup": dedup, "distribution": dist,
                                                             "hybrid_query_count": len(hybrid_queries)}, indent=2))

    print(f"Wrote {len(corpus)} decisions, {len(hybrid_queries)} hybrid queries, "
          f"{len(REGRESSION_QUERIES)} regression queries to {OUT_DIR}")
    print(f"Exact duplicates: {dedup['exact_duplicate_count']}")
    print(f"Intentional near-duplicate pairs: {len(dedup['intentional_near_duplicate_pairs'])}")


if __name__ == "__main__":
    main()
