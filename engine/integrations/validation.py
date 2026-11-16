"""
engine/integrations/validation.py
Security validation for external endpoints to prevent SSRF (Server-Side Request Forgery)
and sanitize incoming configurations.
"""
import ipaddress
import urllib.parse
from typing import Tuple, Optional


# Disallowed hosts and cloud metadata endpoints
BLOCKED_HOSTNAMES = {
    "169.254.169.254",       # AWS/GCP/Azure link-local instance metadata
    "metadata.google.internal",
    "metadata.internal",
    "100.100.100.200",       # Alibaba Cloud metadata
}


def is_safe_external_url(url: str, allow_localhost: bool = True) -> Tuple[bool, str]:
    """
    Validates that a URL is well-formed, uses http/https, and does not target
    dangerous cloud metadata or forbidden internal IP ranges.
    `allow_localhost` defaults to True to support local RAG application services.
    """
    if not url or not isinstance(url, str):
        return False, "URL must be a non-empty string."

    try:
        parsed = urllib.parse.urlparse(url.strip())
    except Exception as e:
        return False, f"Invalid URL format: {str(e)}"

    if parsed.scheme not in ("http", "https"):
        return False, f"Unsupported scheme '{parsed.scheme}'. Only http and https are permitted."

    hostname = parsed.hostname
    if not hostname:
        return False, "URL must contain a valid hostname."

    hostname_lower = hostname.lower()

    if hostname_lower in BLOCKED_HOSTNAMES:
        return False, f"Access to cloud metadata endpoint '{hostname}' is strictly forbidden."

    # Parse IP addresses if given directly
    try:
        ip = ipaddress.ip_address(hostname)
        if ip.is_link_local:
            return False, f"Access to link-local IP '{hostname}' is forbidden (SSRF protection)."
        if ip.is_multicast:
            return False, f"Access to multicast IP '{hostname}' is forbidden."
        if not allow_localhost and (ip.is_loopback or ip.is_private):
            return False, f"Access to internal network IP '{hostname}' is disabled."
    except ValueError:
        # Hostname is a domain name
        pass

    return True, "URL is safe."

