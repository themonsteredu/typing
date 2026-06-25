"""Vendor tooling for the Exam Studio license system.

This is run by YOU (the seller), never shipped to customers. It does two things:

1. ``genkeys`` — create a new Ed25519 keypair. Keep the private key secret;
   paste the printed public key into the app (license.py / license.ts) or set
   ``EXAM_STUDIO_LICENSE_PUBKEY``.

2. ``issue`` — sign a license token for a buyer using your private key.

Examples::

    python tools/license_keygen.py genkeys --out tools/
    python tools/license_keygen.py issue --key tools/license_private_key.pem \\
        --sub "hong@example.com" --plan pro --days 365

The emitted token is what the customer pastes into the app's 활성화(Activate) screen.
"""

from __future__ import annotations

import argparse
import base64
import json
import time
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def cmd_genkeys(args: argparse.Namespace) -> int:
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    key = Ed25519PrivateKey.generate()

    priv_pem = key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    )
    pub_pem = key.public_key().public_bytes(
        serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo
    )
    priv_path = out / "license_private_key.pem"
    priv_path.write_text(priv_pem.decode())
    (out / "license_public_key.pem").write_text(pub_pem.decode())
    print(f"개인키(비밀 보관!): {priv_path}")
    print("앱에 embed 할 공개키 PEM ↓↓↓\n")
    print(pub_pem.decode())
    return 0


def cmd_issue(args: argparse.Namespace) -> int:
    key = serialization.load_pem_private_key(Path(args.key).read_bytes(), password=None)
    if not isinstance(key, Ed25519PrivateKey):
        raise SystemExit("private key is not Ed25519")

    now = int(time.time())
    exp = now + args.days * 86400 if args.days > 0 else 0
    payload = {"sub": args.sub, "plan": args.plan, "iat": now, "exp": exp}
    payload_bytes = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    signature = key.sign(payload_bytes)
    token = f"{_b64url(payload_bytes)}.{_b64url(signature)}"

    human_exp = "무기한" if exp == 0 else time.strftime("%Y-%m-%d", time.localtime(exp))
    print(f"발급 대상: {args.sub}  플랜: {args.plan}  만료: {human_exp}")
    print("\n=== LICENSE KEY (고객에게 전달) ===")
    print(token)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(prog="license_keygen", description="Exam Studio license tooling")
    sub = parser.add_subparsers(dest="command", required=True)

    g = sub.add_parser("genkeys", help="generate a new Ed25519 keypair")
    g.add_argument("--out", default="tools")
    g.set_defaults(func=cmd_genkeys)

    i = sub.add_parser("issue", help="sign a license token for a buyer")
    i.add_argument("--key", required=True, help="path to license_private_key.pem")
    i.add_argument("--sub", required=True, help="buyer name or email")
    i.add_argument("--plan", default="pro")
    i.add_argument("--days", type=int, default=365, help="validity in days (0 = perpetual)")
    i.set_defaults(func=cmd_issue)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
