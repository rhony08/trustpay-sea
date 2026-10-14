"""Generate a dev RS256 keypair if none is mounted (never reuse in prod).

Run as the container entrypoint pre-step: python -m app.generate_dev_keys
"""

from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from app.config import get_settings


def main() -> None:
    settings = get_settings()
    priv_path = Path(settings.jwt_private_key_path)
    pub_path = Path(settings.jwt_public_key_path)

    if priv_path.exists() and pub_path.exists():
        return

    if settings.environment == "prod":
        raise SystemExit("prod requires mounted JWT keys — refusing to self-generate")

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    priv_path.parent.mkdir(parents=True, exist_ok=True)
    priv_path.write_bytes(
        key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )
    )
    pub_path.write_bytes(
        key.public_key().public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
    )
    print(f"generated dev RS256 keypair at {priv_path} / {pub_path}")


if __name__ == "__main__":
    main()
