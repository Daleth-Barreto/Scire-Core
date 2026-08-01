import base64
import json
import os
from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

DEFAULT_ITERATIONS = 150_000
ENVELOPE_VERSION = 1
DEFAULT_KEYS_FILE = Path.home() / ".scire" / "keys.enc"


class SecretStoreError(Exception):
    pass


def derive_key(passphrase: str, salt: bytes, iterations: int = DEFAULT_ITERATIONS) -> bytes:
    kdf = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=salt, iterations=iterations)
    return kdf.derive(passphrase.encode("utf-8"))


def _fernet(passphrase: str, salt: bytes) -> Fernet:
    key = base64.urlsafe_b64encode(derive_key(passphrase, salt))
    return Fernet(key)


def keys_path() -> Path:
    """Location of the encrypted key store (override via SCIRE_KEYS_PATH)."""
    override = os.environ.get("SCIRE_KEYS_PATH")
    return Path(override) if override else DEFAULT_KEYS_FILE


def encrypt_keys(passphrase: str, keys: dict[str, str], path: str | Path | None = None) -> Path:
    target = Path(path) if path is not None else keys_path()
    salt = os.urandom(16)
    token = _fernet(passphrase, salt).encrypt(json.dumps(keys).encode("utf-8"))
    envelope = {
        "version": ENVELOPE_VERSION,
        "salt": salt.hex(),
        "ciphertext": token.decode("ascii"),
    }
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(envelope), encoding="utf-8")
    return target


def decrypt_keys(passphrase: str, path: str | Path | None = None) -> dict[str, str]:
    target = Path(path) if path is not None else keys_path()
    if not target.exists():
        raise SecretStoreError(f"encrypted key store not found at {target}")
    try:
        envelope = json.loads(target.read_text(encoding="utf-8"))
        if envelope.get("version") != ENVELOPE_VERSION:
            raise SecretStoreError("unsupported key store version")
        salt = bytes.fromhex(envelope["salt"])
        token = envelope["ciphertext"].encode("ascii")
        payload = _fernet(passphrase, salt).decrypt(token)
        keys = json.loads(payload.decode("utf-8"))
        if not isinstance(keys, dict):
            raise SecretStoreError("key store payload is not an object")
        return {str(key): str(value) for key, value in keys.items()}
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError, InvalidToken) as exc:
        raise SecretStoreError(
            "cannot decrypt key store (wrong passphrase or corrupted file)"
        ) from exc
