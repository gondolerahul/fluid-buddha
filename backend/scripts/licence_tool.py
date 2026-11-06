"""
Issue and check FluidBuddha licence keys (M3-5). Run by FluidBuddha, not by
customers: issuing needs the private signing key, which never ships.

    # once: a signing key pair (prints the public key to add to app/licence/core.py)
    python scripts/licence_tool.py keygen --kid fb-2027-1 --out ../.licence-keys

    # a licence
    python scripts/licence_tool.py issue --key ../.licence-keys/fb-2026-1.pem --kid fb-2026-1 \\
        --customer "Acme Health" --sites 5 --seats 25 --days 365 [--features byo_model,campaigns] [--grace 14]

    # what a key says (offline, against the keys built into this version)
    python scripts/licence_tool.py verify FBL1.xxxx.yyyy
"""
from __future__ import annotations

import argparse
import base64
import json
import sys
import time
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from cryptography.hazmat.primitives import serialization  # noqa: E402
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey  # noqa: E402

from app.licence import core  # noqa: E402


def keygen(args: argparse.Namespace) -> None:
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    path = out / f"{args.kid}.pem"
    if path.exists():
        sys.exit(f"{path} exists: pick another --kid")
    key = Ed25519PrivateKey.generate()
    path.write_bytes(key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                                       serialization.NoEncryption()))
    pub = key.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
    print(f"private key: {path}  (keep it secret, back it up)")
    print(f'add to PUBLIC_KEYS in app/licence/core.py:\n    "{args.kid}": "{base64.b64encode(pub).decode()}",')


def issue(args: argparse.Namespace) -> None:
    key = serialization.load_pem_private_key(Path(args.key).read_bytes(), password=None)
    if not isinstance(key, Ed25519PrivateKey):
        sys.exit("not an Ed25519 private key")
    now = int(time.time())
    features = [f.strip() for f in args.features.split(",") if f.strip()] if args.features else ["*"]
    unknown = [f for f in features if f != "*" and f not in core.FEATURES]
    if unknown:
        sys.exit(f"unknown features: {unknown}; known: {list(core.FEATURES)}")
    payload = {"kid": args.kid, "lid": args.lid or f"lic_{uuid.uuid4().hex[:12]}", "customer": args.customer,
               "sites": args.sites, "seats": args.seats, "features": features, "iat": now,
               "exp": now + args.days * 86400, "grace_days": args.grace}
    print(core.sign(payload, key))


def verify(args: argparse.Namespace) -> None:
    try:
        lic = core.parse(args.token)
    except core.LicenceError as exc:
        sys.exit(f"invalid: {exc.reason}")
    print(json.dumps(core.state(lic), indent=2, default=str))


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    k = sub.add_parser("keygen")
    k.add_argument("--kid", required=True)
    k.add_argument("--out", default="../.licence-keys")
    k.set_defaults(fn=keygen)
    i = sub.add_parser("issue")
    i.add_argument("--key", required=True)
    i.add_argument("--kid", required=True)
    i.add_argument("--customer", required=True)
    i.add_argument("--sites", type=int, required=True)
    i.add_argument("--seats", type=int, required=True)
    i.add_argument("--days", type=int, default=365)
    i.add_argument("--grace", type=int, default=core.DEFAULT_GRACE_DAYS)
    i.add_argument("--features", default="")
    i.add_argument("--lid", default="")
    i.set_defaults(fn=issue)
    v = sub.add_parser("verify")
    v.add_argument("token")
    v.set_defaults(fn=verify)
    args = p.parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()
