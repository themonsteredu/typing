import base64
import json
import time

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from exam_engine import license as lic


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


@pytest.fixture
def signer(monkeypatch):
    """A throwaway keypair whose public key the module is told to trust."""
    key = Ed25519PrivateKey.generate()
    pub = key.public_key().public_bytes(
        serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo
    ).decode()
    monkeypatch.setenv("EXAM_STUDIO_LICENSE_PUBKEY", pub)
    monkeypatch.delenv("EXAM_STUDIO_DEV", raising=False)

    def issue(sub="buyer@example.com", plan="pro", iat=None, exp=0):
        payload = {"sub": sub, "plan": plan, "iat": iat or int(time.time()), "exp": exp}
        body = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        return f"{_b64url(body)}.{_b64url(key.sign(body))}"

    return issue


def test_valid_perpetual_token(signer):
    info = lic.verify_token(signer(exp=0))
    assert info.valid
    assert info.subject == "buyer@example.com"
    assert info.plan == "pro"
    assert info.expires_at == 0


def test_expired_token(signer):
    info = lic.verify_token(signer(exp=int(time.time()) - 10))
    assert not info.valid
    assert "만료" in info.reason


def test_future_expiry_ok(signer):
    info = lic.verify_token(signer(exp=int(time.time()) + 3600))
    assert info.valid


def test_tampered_payload_rejected(signer):
    token = signer(sub="a@b.com")
    payload_b64, sig = token.split(".")
    forged_payload = json.dumps(
        {"sub": "hacker@evil.com", "plan": "pro", "iat": 1, "exp": 0},
        sort_keys=True, separators=(",", ":"),
    ).encode()
    forged = f"{_b64url(forged_payload)}.{sig}"
    assert not lic.verify_token(forged).valid


def test_wrong_key_rejected(monkeypatch, signer):
    token = signer()
    # Swap the trusted public key to a different one -> signature no longer verifies.
    other = Ed25519PrivateKey.generate().public_key().public_bytes(
        serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo
    ).decode()
    monkeypatch.setenv("EXAM_STUDIO_LICENSE_PUBKEY", other)
    assert not lic.verify_token(token).valid


def test_garbage_token(signer):
    assert not lic.verify_token("not-a-token").valid
    assert not lic.verify_token("").valid


def test_activate_and_load(tmp_path, monkeypatch, signer):
    monkeypatch.setenv("EXAM_STUDIO_LICENSE", str(tmp_path / "license.json"))
    token = signer()
    info = lic.activate(token)
    assert info.valid
    assert lic.load().valid
    assert lic.is_licensed()


def test_activate_rejects_invalid(tmp_path, monkeypatch, signer):
    monkeypatch.setenv("EXAM_STUDIO_LICENSE", str(tmp_path / "license.json"))
    with pytest.raises(ValueError):
        lic.activate("bogus.token")


def test_dev_bypass(monkeypatch, tmp_path):
    monkeypatch.setenv("EXAM_STUDIO_LICENSE", str(tmp_path / "nope.json"))
    monkeypatch.setenv("EXAM_STUDIO_DEV", "1")
    assert lic.is_licensed()
