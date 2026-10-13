import pytest
from pydantic import ValidationError

from src.App.Settings import Settings


def test_upload_limit_rejects_values_above_ingress_cap() -> None:
    with pytest.raises(ValidationError, match="95 MiB ingress cap"):
        Settings(opencode_upload_max_bytes=95 * 1024 * 1024 + 1)


def test_upload_limit_allows_smaller_deployment_cap() -> None:
    assert Settings(opencode_upload_max_bytes=10 * 1024 * 1024).opencode_upload_max_bytes == 10 * 1024 * 1024
