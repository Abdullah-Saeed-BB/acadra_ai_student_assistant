"""Store Gmail refresh tokens in the operating system credential manager."""

import asyncio
from uuid import uuid4

import keyring

SERVICE_NAME = "acadra.gmail"


def _require_secure_backend() -> None:
    backend = keyring.get_keyring()
    module = type(backend).__module__
    if not module.startswith(("keyring.backends.Windows", "keyring.backends.macOS", "keyring.backends.SecretService")):
        raise RuntimeError("A supported operating system credential store is unavailable.")


async def save_gmail_refresh_token(token: str) -> str:
    _require_secure_backend()
    secret_id = str(uuid4())
    await asyncio.to_thread(keyring.set_password, SERVICE_NAME, secret_id, token)
    return f"keyring:{SERVICE_NAME}:{secret_id}"


async def delete_gmail_refresh_token(credential_ref: str) -> None:
    _require_secure_backend()
    prefix = f"keyring:{SERVICE_NAME}:"
    if not credential_ref.startswith(prefix):
        raise ValueError("Invalid Gmail credential reference.")
    await asyncio.to_thread(keyring.delete_password, SERVICE_NAME, credential_ref[len(prefix):])
