"""
Converts Slack/Gmail/Notion events into the common EventEnvelope shape.
"""
from __future__ import annotations
from uuid import UUID
from typing import Dict, Any
from modules.ingestion.envelope.schemas import EventEnvelope

def normalize_gmail_message(msg: Dict[str, Any], tenant_id: UUID) -> EventEnvelope:
    """Normalize a raw Gmail message response into an EventEnvelope.
    
    The raw Gmail message structure contains headers, a payload body, etc.
    """
    headers = msg.get("payload", {}).get("headers", [])
    
    # Helper to retrieve headers
    def get_header(name: str) -> str:
        for h in headers:
            if h.get("name", "").lower() == name.lower():
                return h.get("value", "")
        return ""

    from_header = get_header("From")
    subject = get_header("Subject")
    
    # Try to extract the body of the email
    body = ""
    payload = msg.get("payload", {})
    parts = payload.get("parts", [])
    
    # If the payload has no parts but has a body, read from body data
    if "body" in payload and payload["body"].get("data"):
        import base64
        try:
            body = base64.urlsafe_b64decode(payload["body"]["data"]).decode("utf-8", errors="ignore")
        except Exception:
            pass
    elif parts:
        # DFS find plain text body part
        def find_body(parts_list):
            for part in parts_list:
                mime_type = part.get("mimeType", "")
                if mime_type == "text/plain" and part.get("body", {}).get("data"):
                    import base64
                    try:
                        return base64.urlsafe_b64decode(part["body"]["data"]).decode("utf-8", errors="ignore")
                    except Exception:
                        pass
                elif part.get("parts"):
                    found = find_body(part["parts"])
                    if found:
                        return found
            return ""
        body = find_body(parts)
        
    # Fallback to snippet if body is still empty
    if not body:
        body = msg.get("snippet", "")

    # Clean actor from "Name <email@domain.com>" to just "email@domain.com" if possible
    actor = from_header
    if "<" in from_header and ">" in from_header:
        actor = from_header.split("<")[1].split(">")[0].strip()

    raw_content = {
        "subject": subject,
        "body": body,
        "from": from_header,
        "to": get_header("To"),
        "date": get_header("Date"),
        "snippet": msg.get("snippet", ""),
        "id": msg.get("id"),
        "threadId": msg.get("threadId"),
    }
    
    return EventEnvelope(
        tenant_id=tenant_id,
        source="gmail",
        source_id=msg.get("id"),
        actor=actor,
        thread_ref=msg.get("threadId"),
        permission_scope=[],   # empty = visible to whole workspace (spec 1.4 default)
        raw_content=raw_content
    )
