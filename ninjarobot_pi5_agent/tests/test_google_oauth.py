from __future__ import annotations

import asyncio
import json
import stat
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from google.oauth2.credentials import Credentials
from ninjarobot_pi5_agent.cloud_common import CloudAuthenticationError
from ninjarobot_pi5_agent.cloud_registry import ConfiguredProviderRegistry
from ninjarobot_pi5_agent.google_oauth import (
    GEMINI_SCOPES,
    GoogleOAuthCredential,
    gemini_credential_path,
    save_google_credentials,
)
from ninjarobot_pi5_agent.provider_auth import (
    _gemini_web_login,
    _validate_google_client_file,
    _validate_google_redirect,
    web_logout,
)
from ninjarobot_pi5_agent.secrets import SecretStore

from ninjarobot_pi5_ide import load_robot_config, save_robot_config

ROOT = Path(__file__).resolve().parents[2]
EXAMPLE = ROOT / "config" / "ninjarobot_pi5.toml.example"

CLIENT_DOCUMENT = {
    "installed": {
        "client_id": "client-id.apps.googleusercontent.com",
        "client_secret": "client-secret",
        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
        "token_uri": "https://oauth2.googleapis.com/token",
        "redirect_uris": ["http://localhost"],
    }
}


def _credentials(*, token: str = "access-token", expired: bool = False) -> Credentials:
    return Credentials(
        token=token,
        refresh_token="refresh-token",
        token_uri="https://oauth2.googleapis.com/token",
        client_id="client-id.apps.googleusercontent.com",
        client_secret="client-secret",
        scopes=GEMINI_SCOPES,
        expiry=datetime.now(UTC) + (timedelta(minutes=-5) if expired else timedelta(hours=1)),
    )


def _oauth_config(tmp_path: Path) -> Path:
    config = load_robot_config(EXAMPLE)
    payload = config.model_dump(mode="python")
    payload["providers"]["gemini"]["auth_method"] = "oauth"
    payload["providers"]["gemini"]["project_id"] = "test-project"
    config_path = tmp_path / "config.toml"
    save_robot_config(type(config).model_validate(payload), config_path, overwrite=False)
    return config_path


def test_provider_id_cannot_escape_oauth_directory(tmp_path: Path) -> None:
    secret_file = tmp_path / "private" / "secrets.env"

    credential_file = gemini_credential_path(secret_file, "../../outside")

    assert credential_file.parent == secret_file.parent / "oauth"
    assert credential_file.name.startswith("gemini-")
    assert ".." not in credential_file.name


def test_credentials_are_saved_atomically_with_owner_only_permissions(
    tmp_path: Path,
) -> None:
    credential_file = tmp_path / "oauth" / "gemini.json"

    save_google_credentials(credential_file, _credentials())

    assert stat.S_IMODE(credential_file.stat().st_mode) == 0o600
    assert stat.S_IMODE(credential_file.parent.stat().st_mode) == 0o700
    assert json.loads(credential_file.read_text(encoding="utf-8"))["token"] == "access-token"


def test_credentials_refuse_symbolic_link_destination(tmp_path: Path) -> None:
    target = tmp_path / "target.json"
    target.write_text("{}\n", encoding="utf-8")
    credential_file = tmp_path / "credential.json"
    credential_file.symlink_to(target)

    with pytest.raises(CloudAuthenticationError, match="symbolic-link"):
        save_google_credentials(credential_file, _credentials())


def test_credentials_refuse_symbolic_link_directory(tmp_path: Path) -> None:
    target = tmp_path / "target"
    target.mkdir()
    oauth_directory = tmp_path / "oauth"
    oauth_directory.symlink_to(target, target_is_directory=True)

    with pytest.raises(CloudAuthenticationError, match="symbolic-link OAuth directory"):
        save_google_credentials(oauth_directory / "credential.json", _credentials())


def test_google_oauth_credential_returns_bearer_without_disclosing_file(
    tmp_path: Path,
) -> None:
    credential_file = tmp_path / "oauth.json"
    save_google_credentials(credential_file, _credentials())
    source = GoogleOAuthCredential(credential_file)

    assert asyncio.run(source.headers()) == {"Authorization": "Bearer access-token"}
    assert source.status() == {
        "method": "oauth",
        "credential_store": "ninjarobot_pi5",
        "configured": True,
    }
    assert "access-token" not in repr(source.status())


def test_registry_reports_native_gemini_credential_without_secret(
    tmp_path: Path,
) -> None:
    config_path = _oauth_config(tmp_path)
    secret_file = tmp_path / "secrets.env"
    registry = ConfiguredProviderRegistry(config_path, SecretStore(secret_file))

    assert registry.credential_status("gemini") == {
        "method": "oauth",
        "credential_store": "ninjarobot_pi5",
        "configured": False,
    }
    save_google_credentials(
        gemini_credential_path(secret_file, "gemini"),
        _credentials(),
    )
    assert registry.credential_status("gemini")["configured"] is True


def test_google_oauth_credential_refreshes_and_resaves(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    credential_file = tmp_path / "oauth.json"
    save_google_credentials(credential_file, _credentials(expired=True))

    def refresh(credentials: Credentials, _request: object) -> None:
        credentials.token = "refreshed-token"
        credentials.expiry = datetime.now(UTC) + timedelta(hours=1)

    monkeypatch.setattr(Credentials, "refresh", refresh)
    source = GoogleOAuthCredential(credential_file)

    assert asyncio.run(source.headers()) == {"Authorization": "Bearer refreshed-token"}
    assert json.loads(credential_file.read_text(encoding="utf-8"))["token"] == "refreshed-token"


def test_google_oauth_credential_rejects_unsafe_permissions(tmp_path: Path) -> None:
    credential_file = tmp_path / "oauth.json"
    save_google_credentials(credential_file, _credentials())
    credential_file.chmod(0o644)

    with pytest.raises(CloudAuthenticationError, match="chmod 600"):
        asyncio.run(GoogleOAuthCredential(credential_file).headers())


@pytest.mark.parametrize(
    "response",
    (
        "https://localhost:8080/?state=expected&code=code",
        "http://evil.example:8080/?state=expected&code=code",
        "http://localhost:8081/?state=expected&code=code",
        "http://localhost:8080/?state=wrong&code=code",
        "http://localhost:8080/?state=expected",
    ),
)
def test_google_redirect_validation_rejects_untrusted_response(response: str) -> None:
    with pytest.raises(CloudAuthenticationError, match="does not match"):
        _validate_google_redirect(response, "expected")


def test_google_redirect_validation_accepts_expected_loopback_response() -> None:
    _validate_google_redirect(
        "http://localhost:8080/?state=expected&code=authorization-code",
        "expected",
    )


def test_google_client_validation_rejects_web_application(tmp_path: Path) -> None:
    client_file = tmp_path / "client.json"
    client_file.write_text('{"web": {}}\n', encoding="utf-8")

    with pytest.raises(CloudAuthenticationError, match="Desktop app"):
        _validate_google_client_file(client_file)


def test_headless_gemini_login_rejects_symbolic_link_client(
    tmp_path: Path,
) -> None:
    target = tmp_path / "client-target.json"
    target.write_text(json.dumps(CLIENT_DOCUMENT), encoding="utf-8")
    client_file = tmp_path / "client.json"
    client_file.symlink_to(target)

    with pytest.raises(CloudAuthenticationError, match="symbolic-link"):
        _gemini_web_login(client_file, tmp_path / "credential.json")


def test_headless_gemini_login_saves_flow_credentials(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client_file = tmp_path / "client.json"
    client_file.write_text(json.dumps(CLIENT_DOCUMENT), encoding="utf-8")
    credential_file = tmp_path / "oauth" / "gemini.json"

    class FakeFlow:
        redirect_uri: str | None = None
        credentials = _credentials()

        def authorization_url(self, **_kwargs: object) -> tuple[str, str]:
            return "https://accounts.google.com/o/oauth2/auth", "expected"

        def fetch_token(self, *, authorization_response: str) -> None:
            assert authorization_response.endswith("state=expected&code=authorization-code")

    monkeypatch.setattr(
        "ninjarobot_pi5_agent.provider_auth.InstalledAppFlow.from_client_secrets_file",
        lambda *_args, **_kwargs: FakeFlow(),
    )
    monkeypatch.setattr(
        "ninjarobot_pi5_agent.provider_auth.getpass.getpass",
        lambda _prompt: "http://localhost:8080/?state=expected&code=authorization-code",
    )

    _gemini_web_login(client_file, credential_file)

    assert json.loads(credential_file.read_text(encoding="utf-8"))["token"] == "access-token"


def test_gemini_logout_removes_only_managed_credential(tmp_path: Path) -> None:
    config_path = _oauth_config(tmp_path)
    secret_file = tmp_path / "secrets.env"
    credential_file = gemini_credential_path(secret_file, "gemini")
    save_google_credentials(credential_file, _credentials())

    removed = asyncio.run(
        web_logout(config_path, "gemini", secret_file=secret_file),
    )
    removed_again = asyncio.run(
        web_logout(config_path, "gemini", secret_file=secret_file),
    )

    assert removed is True
    assert removed_again is False
    assert not credential_file.exists()
