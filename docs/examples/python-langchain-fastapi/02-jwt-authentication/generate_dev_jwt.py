from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone

import jwt


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate a short-lived local dev JWT (HS256).")
    parser.add_argument("--secret", default="change-me-in-local-env")
    parser.add_argument("--subject", default="user-123")
    parser.add_argument("--issuer", default="https://issuer.example.com")
    parser.add_argument("--audience", default="runtime")
    parser.add_argument("--ttl-seconds", type=int, default=300)
    args = parser.parse_args()

    now = datetime.now(tz=timezone.utc)

    claims = {
        "sub": args.subject,
        "iss": args.issuer,
        "aud": args.audience,
        "iat": int(now.timestamp()),
        "nbf": int(now.timestamp()),
        "exp": int((now + timedelta(seconds=args.ttl_seconds)).timestamp()),
    }

    token = jwt.encode(claims, args.secret, algorithm="HS256")
    print(token)


if __name__ == "__main__":
    main()
