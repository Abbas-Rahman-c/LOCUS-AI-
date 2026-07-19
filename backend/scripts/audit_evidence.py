"""
Audit evidence collector for Auth & Tenant-Scoped Session.
Generates a real token, decodes it, prints its claims, and prints code references.
"""
from __future__ import annotations

import os
import sys
import uuid
import time
from jose import jwt

# Set up path to import internal modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))

from modules.auth.service import issue_tenant_jwt, verify_tenant_jwt
from app.dependencies import TenantContext

os.environ["APP_SECRET_KEY"] = "test-secret-key-for-unit-tests-must-be-at-least-32-chars-long"

def generate_and_decode_audit_token():
    print("--- 1. Token Claim Verification ---")
    tenant_id = str(uuid.uuid4())
    user_id = str(uuid.uuid4())
    role = "owner"
    
    # Generate the token using the service layer
    token = issue_tenant_jwt(user_id=user_id, tenant_id=tenant_id, role=role, ttl=3600)
    print(f"Generated Session Token (JWT):\n{token}\n")
    
    # Decode and print payload
    payload = verify_tenant_jwt(token)
    print("Decoded Claims:")
    for claim, val in payload.items():
        print(f"  {claim}: {val}")
    
    assert payload["tenant_id"] == tenant_id
    assert payload["sub"] == user_id
    assert payload["role"] == role
    assert payload["iss"] == "locus-ai"
    print("Verification: SUCCESS - All tenant and sub claims are present and correct.\n")

if __name__ == "__main__":
    generate_and_decode_audit_token()
