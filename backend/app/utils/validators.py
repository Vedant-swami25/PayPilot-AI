from __future__ import annotations

import ipaddress
import re
import uuid
from urllib.parse import urlparse


_CONTROL_CHAR_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_PROMPT_TAG_RE = re.compile(r"</?\s*(system|assistant|user|instruction|prompt)[^>]*>", re.IGNORECASE)


def normalize_email(email: str) -> str:
    """Normalize an email address for consistent lookup and uniqueness."""
    return email.strip().lower()


def is_valid_uuid(value: str) -> bool:
    """Return True if value is a valid UUID string."""
    try:
        uuid.UUID(str(value))
        return True
    except (ValueError, TypeError, AttributeError):
        return False


def validate_safe_http_url(url: str | None) -> str | None:
    """Validate an untrusted external URL uses http(s) and is not loopback/private SSRF."""
    if url is None:
        return None
    cleaned = url.strip()
    if not cleaned:
        return None
    parsed = urlparse(cleaned)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError(f"Invalid HTTP(S) URL: '{url}'")
    host = (parsed.hostname or "").strip().lower()
    if not host or host in {"localhost", "localhost.localdomain"} or host.endswith((".local", ".internal")):
        raise ValueError(f"Disallowed local/internal host in URL: '{url}'")
    try:
        ip = ipaddress.ip_address(host)
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast:
            raise ValueError(f"Disallowed non-public IP address in URL: '{url}'")
    except ValueError as exc:
        if "Disallowed" in str(exc):
            raise
    return cleaned


def sanitize_search_query(query: str, max_length: int = 200) -> str:
    """Trim and bound a user search query."""
    cleaned = _CONTROL_CHAR_RE.sub("", " ".join(query.strip().split()))
    if not cleaned:
        raise ValueError("Search query cannot be empty.")
    return cleaned[:max_length]


def sanitize_untrusted_text(text: str | None, max_length: int = 1000) -> str:
    """Sanitize untrusted external merchant/product text before passing to LLMs."""
    if not text:
        return ""
    cleaned = _CONTROL_CHAR_RE.sub(" ", str(text))
    cleaned = _PROMPT_TAG_RE.sub("", cleaned)
    cleaned = " ".join(cleaned.split())
    return cleaned[:max_length]

