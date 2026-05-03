import base64
import hashlib
import hmac
import json
import re
from typing import Any

from cryptography.fernet import Fernet, InvalidToken
from pydantic import SecretStr


class EncryptionError(RuntimeError):
    pass


_PHI_PATTERNS = [
    re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
    re.compile(r"\b\d{3}[-.\s]\d{3}[-.\s]\d{4}\b"),
    re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE),
    re.compile(r"\b(?:19|20)\d{2}-\d{2}-\d{2}\b"),
    re.compile(r"\b(?:dob|date of birth|mrn|medical record number)\b", re.IGNORECASE),
]


class PhiCipher:
    def __init__(self, encryption_key: SecretStr, key_id: str) -> None:
        self.key_id = key_id
        self._fernet = Fernet(encryption_key.get_secret_value().encode("ascii"))
        self._fingerprint_key = _fingerprint_key(encryption_key)

    def encrypt_json(self, payload: dict[str, Any]) -> bytes:
        plaintext = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        return self._fernet.encrypt(plaintext)

    def decrypt_json(self, ciphertext: bytes) -> dict[str, Any]:
        try:
            plaintext = self._fernet.decrypt(ciphertext)
        except InvalidToken as exc:
            raise EncryptionError("Encrypted payload could not be decrypted") from exc

        decoded = json.loads(plaintext.decode("utf-8"))
        if not isinstance(decoded, dict):
            raise EncryptionError("Encrypted payload did not decode to an object")
        return decoded

    def fingerprint(self, value: str) -> str:
        digest = hmac.new(self._fingerprint_key, value.encode("utf-8"), hashlib.sha256).hexdigest()
        return digest


def assert_metadata_payload_is_phi_safe(payload: dict[str, Any]) -> None:
    serialized = json.dumps(payload, sort_keys=True, default=str)
    for pattern in _PHI_PATTERNS:
        if pattern.search(serialized):
            raise ValueError("Audit metadata appears to contain raw PHI")


def _fingerprint_key(encryption_key: SecretStr) -> bytes:
    decoded = base64.urlsafe_b64decode(encryption_key.get_secret_value().encode("ascii"))
    return hashlib.sha256(decoded + b":agentforge-phi-fingerprint").digest()
