import pytest

from backend.core.secrets import (
    SecretStoreError,
    decrypt_keys,
    derive_key,
    encrypt_keys,
)


def test_roundtrip(tmp_path):
    path = tmp_path / "keys.enc"
    keys = {"OPENAI_API_KEY": "sk-123", "GITHUB_TOKEN": "ghp_abc"}
    encrypt_keys("passphrase", keys, path)
    assert decrypt_keys("passphrase", path) == keys


def test_wrong_passphrase_raises(tmp_path):
    path = tmp_path / "keys.enc"
    encrypt_keys("right", {"OPENAI_API_KEY": "sk-123"}, path)
    with pytest.raises(SecretStoreError):
        decrypt_keys("wrong", path)


def test_tampered_file_raises(tmp_path):
    path = tmp_path / "keys.enc"
    encrypt_keys("pass", {"OPENAI_API_KEY": "sk-123"}, path)
    data = bytearray(path.read_bytes())
    for i in range(len(data) - 4, len(data)):
        data[i] ^= 0xFF
    path.write_bytes(bytes(data))
    with pytest.raises(SecretStoreError):
        decrypt_keys("pass", path)


def test_missing_file_raises(tmp_path):
    with pytest.raises(SecretStoreError):
        decrypt_keys("pass", tmp_path / "nope.enc")


def test_derive_key_deterministic():
    k1 = derive_key("passphrase", b"salt")
    k2 = derive_key("passphrase", b"salt")
    k3 = derive_key("passphrase", b"other")
    assert k1 == k2 and k1 != k3


def test_file_not_plaintext(tmp_path):
    path = tmp_path / "keys.enc"
    encrypt_keys("pass", {"OPENAI_API_KEY": "sk-123"}, path)
    assert b"sk-123" not in path.read_bytes()


def test_create_parent_dirs(tmp_path):
    path = tmp_path / "nested" / "dir" / "keys.enc"
    encrypt_keys("pass", {"OPENAI_API_KEY": "sk-123"}, path)
    assert path.exists()
    assert decrypt_keys("pass", path) == {"OPENAI_API_KEY": "sk-123"}
