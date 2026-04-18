from __future__ import annotations

from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.db import models


class EncryptedTextField(models.TextField):
    description = "Text field encrypted with Fernet"

    @staticmethod
    def _get_fernet() -> Fernet:
        key = settings.FIELD_ENCRYPTION_KEY
        if not key:
            raise ImproperlyConfigured("FIELD_ENCRYPTION_KEY is required for encrypted fields")
        return Fernet(key.encode())

    def get_prep_value(self, value: str | None) -> str | None:
        if value in (None, ""):
            return value
        fernet = self._get_fernet()
        return fernet.encrypt(value.encode()).decode()

    def from_db_value(self, value: str | None, expression, connection) -> str | None:
        if value in (None, ""):
            return value
        fernet = self._get_fernet()
        try:
            return fernet.decrypt(value.encode()).decode()
        except InvalidToken as exc:
            raise ImproperlyConfigured("Failed to decrypt value. Check FIELD_ENCRYPTION_KEY.") from exc

    def to_python(self, value: str | None) -> str | None:
        if value in (None, ""):
            return value
        if isinstance(value, str) and value.startswith("gAAAA"):
            try:
                return self._get_fernet().decrypt(value.encode()).decode()
            except InvalidToken:
                return value
        return value
