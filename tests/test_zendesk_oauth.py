from pathlib import Path

from zendesk_confluence_migrator.config import ExportSettings, ZendeskSettings
from zendesk_confluence_migrator.zendesk_client import ZendeskClient


def test_client_credentials_are_exchanged_for_a_bearer_token(monkeypatch):
    captured = {}

    class Response:
        status_code = 200

        def json(self):
            return {"access_token": "access-1"}

    def fake_post(url, json, headers, timeout):
        captured["url"] = url
        captured["json"] = json
        captured["timeout"] = timeout
        return Response()

    monkeypatch.setattr("zendesk_confluence_migrator.zendesk_client.requests.post", fake_post)
    client = ZendeskClient(_settings(client_id="migration-client", client_secret="migration-secret"), _export())

    assert captured["url"] == "https://acme.zendesk.com/oauth/tokens"
    assert captured["json"]["grant_type"] == "client_credentials"
    assert captured["json"]["client_id"] == "migration-client"
    assert captured["json"]["client_secret"] == "migration-secret"
    assert captured["json"]["scope"] == "hc:read"
    assert captured["json"]["expires_in"] == 172800
    assert client._authenticated_session.headers["Authorization"] == "Bearer access-1"
    assert client._authenticated_session.auth is None


def test_email_login_does_not_contact_the_oauth_endpoint(monkeypatch):
    def fake_post(*_args, **_kwargs):
        raise AssertionError("email login must not call the OAuth token URL")

    monkeypatch.setattr("zendesk_confluence_migrator.zendesk_client.requests.post", fake_post)
    client = ZendeskClient(_settings(email="person@acme.com", api_token="zendesk-token"), _export())

    assert client._authenticated_session.auth.username == "person@acme.com/token"
    assert client._authenticated_session.auth.password == "zendesk-token"


def test_refused_client_credentials_do_not_repeat_the_secret(monkeypatch):
    class Response:
        status_code = 401

        def json(self):
            return {"error": "invalid_client", "error_description": "credentials are wrong"}

    monkeypatch.setattr(
        "zendesk_confluence_migrator.zendesk_client.requests.post",
        lambda *args, **kwargs: Response(),
    )
    try:
        ZendeskClient(_settings(client_id="migration-client", client_secret="super-secret"), _export())
    except RuntimeError as exc:
        message = str(exc)
    else:
        raise AssertionError("expected Zendesk to refuse the client")
    assert "super-secret" not in message
    assert "ZENDESK_OAUTH_CLIENT_ID" in message
    assert "credentials are wrong" in message


def _settings(**overrides) -> ZendeskSettings:
    values = {
        "category_url": "https://acme.zendesk.com/hc/en-gb/categories/999-help",
        "origin": "https://acme.zendesk.com",
        "host": "acme.zendesk.com",
        "locale": "en-gb",
        "category_id": 999,
        "email": None,
        "api_token": None,
        "oauth_client_id": None,
        "oauth_client_secret": None,
    }
    values.update(overrides)
    if "client_id" in overrides:
        values["oauth_client_id"] = overrides["client_id"]
    if "client_secret" in overrides:
        values["oauth_client_secret"] = overrides["client_secret"]
    values.pop("client_id", None)
    values.pop("client_secret", None)
    return ZendeskSettings(**values)


def _export() -> ExportSettings:
    return ExportSettings(
        output_dir=Path("output"),
        include_drafts=True,
        allow_partial_export=False,
        fail_on_unresolved_zendesk_links=False,
        request_timeout_seconds=30,
        article_limit=None,
    )
