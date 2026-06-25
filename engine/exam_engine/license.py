"""Offline license verification (Ed25519 signed tokens).

A license **token** is::

    base64url(payload_json) + "." + base64url(signature)

where ``payload_json`` is a compact, sorted-key JSON object and ``signature`` is
an Ed25519 signature over those exact JSON bytes. The vendor signs tokens with a
private key (see ``tools/license_keygen.py``); the app ships only the public key,
so tokens are verified **without any license server** — suitable for a
distributed / self-hosted product.

Payload fields::

    {"sub": "buyer name/email", "plan": "pro", "iat": <epoch>, "exp": <epoch|0>}

``exp == 0`` means a perpetual license. The same token is verified identically by
the Node studio (studio/lib/license.ts) so either side can gate features.
"""

from __future__ import annotations

import base64
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

# Vendor public key. Override with EXAM_STUDIO_LICENSE_PUBKEY (PEM) to use your
# own signing key without editing code.
DEFAULT_PUBLIC_KEY_PEM = """-----BEGIN PUBLIC KEY-----
MCowBQYDK2VwAyEAxlMS4QobYlKgonzF55hHhbxWzwOtyOZKJGaXHTKXqI8=
-----END PUBLIC KEY-----"""


def license_path() -> Path:
    override = os.environ.get("EXAM_STUDIO_LICENSE")
    if override:
        return Path(override).expanduser()
    return Path.home() / ".exam-studio" / "license.json"


@dataclass
class LicenseInfo:
    valid: bool
    reason: str = ""
    subject: str = ""
    plan: str = ""
    issued_at: int = 0
    expires_at: int = 0  # 0 = perpetual

    def to_dict(self) -> Dict[str, Any]:
        return {
            "valid": self.valid,
            "reason": self.reason,
            "subject": self.subject,
            "plan": self.plan,
            "issuedAt": self.issued_at,
            "expiresAt": self.expires_at,
        }


def _b64url_decode(data: str) -> bytes:
    pad = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(data + pad)


def _public_key() -> Ed25519PublicKey:
    pem = os.environ.get("EXAM_STUDIO_LICENSE_PUBKEY") or DEFAULT_PUBLIC_KEY_PEM
    key = serialization.load_pem_public_key(pem.encode("utf-8"))
    if not isinstance(key, Ed25519PublicKey):
        raise ValueError("license public key is not Ed25519")
    return key


def verify_token(token: str, now: Optional[int] = None) -> LicenseInfo:
    """Verify a license token's signature and expiry."""
    import time

    now = int(time.time()) if now is None else now
    token = (token or "").strip()
    if not token or "." not in token:
        return LicenseInfo(False, "라이선스 키 형식이 올바르지 않습니다.")

    payload_b64, sig_b64 = token.rsplit(".", 1)
    try:
        payload_bytes = _b64url_decode(payload_b64)
        signature = _b64url_decode(sig_b64)
    except Exception:
        return LicenseInfo(False, "라이선스 키를 디코딩할 수 없습니다.")

    try:
        _public_key().verify(signature, payload_bytes)
    except InvalidSignature:
        return LicenseInfo(False, "서명이 유효하지 않습니다(위조되었거나 다른 키로 발급됨).")
    except Exception as exc:
        return LicenseInfo(False, f"검증 오류: {exc}")

    try:
        payload = json.loads(payload_bytes.decode("utf-8"))
    except Exception:
        return LicenseInfo(False, "라이선스 내용을 읽을 수 없습니다.")

    exp = int(payload.get("exp", 0) or 0)
    if exp and now > exp:
        return LicenseInfo(False, "라이선스가 만료되었습니다.", subject=payload.get("sub", ""),
                           plan=payload.get("plan", ""), expires_at=exp)

    return LicenseInfo(
        True,
        "",
        subject=payload.get("sub", ""),
        plan=payload.get("plan", ""),
        issued_at=int(payload.get("iat", 0) or 0),
        expires_at=exp,
    )


def load() -> LicenseInfo:
    """Verify the stored license (if any)."""
    path = license_path()
    if not path.exists():
        return LicenseInfo(False, "라이선스가 등록되지 않았습니다.")
    try:
        token = json.loads(path.read_text(encoding="utf-8")).get("token", "")
    except Exception:
        return LicenseInfo(False, "라이선스 파일을 읽을 수 없습니다.")
    return verify_token(token)


def activate(token: str) -> LicenseInfo:
    """Verify and persist a license token. Raises ValueError if invalid."""
    info = verify_token(token)
    if not info.valid:
        raise ValueError(info.reason)
    path = license_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"token": token.strip()}, ensure_ascii=False, indent=2), encoding="utf-8")
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass
    return info


def is_licensed() -> bool:
    # A license check can be bypassed for development with EXAM_STUDIO_DEV=1.
    if os.environ.get("EXAM_STUDIO_DEV") == "1":
        return True
    return load().valid


__all__ = ["LicenseInfo", "verify_token", "load", "activate", "is_licensed", "license_path"]
