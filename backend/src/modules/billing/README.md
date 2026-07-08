# Billing Module — Placeholder Only

> [!CAUTION]
> **Billing is owned by a separate team.**
> This folder is a placeholder. Do NOT add implementation code here without
> explicit confirmation from the backend lead first.

## Ownership

- **Team:** External Billing Team (separate from the Locus AI Backend team)
- **Backend Lead approval required** before any code is added here

## What lives here (placeholder stubs only)

| File | Status |
|---|---|
| `router.py` | Stub — do not wire into app/main.py |
| `service.py` | Stub — do not implement |
| `webhook.py` | Stub — do not implement |
| `schemas.py` | Stub — types only if needed by other modules |

## What NOT to do

- Do NOT register billing routes in `app/main.py`
- Do NOT import from `modules/billing/` in any other module
- Do NOT add Stripe webhook handling logic here without team sign-off
