# Authored by Vedanti Kanade
# Written by: [Your Name] - SJSU CMPE-272
import hmac
import hashlib

def verify_github_signature(payload_body: bytes, secret: str, signature_header: str) -> bool:
    """
    Validates GitHub HMAC SHA-256 signature using constant-time comparison.
    Header format: 'sha256=<hex_digest>'
    """
    if not signature_header or not signature_header.startswith("sha256="):
        return False

    expected_signature = signature_header.split("sha256=")[1]
    computed_hmac = hmac.new(
        secret.encode("utf-8"),
        msg=payload_body,
        digestmod=hashlib.sha256
    ).hexdigest()

    return hmac.compare_digest(computed_hmac, expected_signature)