from pathlib import Path

from zendesk_confluence_migrator.config import ConfluenceSettings, ExportSettings
from zendesk_confluence_migrator.confluence_client import ConfluenceClient


def test_client_credentials_use_the_cloud_api_and_a_bearer_token(monkeypatch):
    calls = []

    class Response:
        def __init__(self, status_code, payload):
            self.status_code = status_code
            self._payload = payload

        def json(self):
            return self._payload

    def fake_get(url, timeout):
        calls.append(("get", url, timeout))
        return Response(200, {"cloudId": "cloud-1"})

    def fake_post(url, data, headers, timeout):
        calls.append(("post", url, data, timeout))
        return Response(200, {"access_token": "access-1", "expires_in": 3600})

    monkeypatch.setattr("zendesk_confluence_migrator.confluence_client.requests.get", fake_get)
    monkeypatch.setattr("zendesk_confluence_migrator.confluence_client.requests.post", fake_post)
    client = ConfluenceClient(
        _settings(client_id="confluence-client", client_secret="confluence-secret"),
        _export(),
    )
    seen = {}

    def fake_request(method, url, **kwargs):
        seen["url"] = url

        class ApiResponse:
            status_code = 200
            headers: dict[str, str] = {}

            def json(self):
                return {"id": "1"}

        return ApiResponse()

    client._session.request = fake_request
    client.get_space("OPS")

    assert client._api_base == "https://api.atlassian.com/ex/confluence/cloud-1/wiki"
    assert calls[0][0] == "get"
    assert calls[0][1] == "https://acme.atlassian.net/_edge/tenant_info"
    assert calls[1][1] == "https://auth.atlassian.com/oauth/token"
    assert calls[1][2]["grant_type"] == "client_credentials"
    assert calls[1][2]["client_secret"] == "confluence-secret"
    assert client._session.headers["Authorization"] == "Bearer access-1"
    assert seen["url"] == "https://api.atlassian.com/ex/confluence/cloud-1/wiki/rest/api/space/OPS"


def test_email_login_stays_on_the_site_url(monkeypatch):
    def fail(*_args, **_kwargs):
        raise AssertionError("email login must not call the OAuth token URL")

    monkeypatch.setattr("zendesk_confluence_migrator.confluence_client.requests.get", fail)
    monkeypatch.setattr("zendesk_confluence_migrator.confluence_client.requests.post", fail)
    client = ConfluenceClient(_settings(email="person@acme.com", api_token="atlas-token"), _export())

    assert client._api_base == "https://acme.atlassian.net/wiki"
    assert client._session.auth.username == "person@acme.com"
    assert client._session.auth.password == "atlas-token"


def test_refused_client_credentials_do_not_repeat_the_secret(monkeypatch):
    class Response:
        status_code = 401

        def json(self):
            return {"error": "invalid_client", "error_description": "credentials are wrong"}

    monkeypatch.setattr(
        "zendesk_confluence_migrator.confluence_client.requests.get",
        lambda *args, **kwargs: type("R", (), {"status_code": 200, "json": lambda self: {"cloudId": "cloud-1"}})(),
    )
    monkeypatch.setattr(
        "zendesk_confluence_migrator.confluence_client.requests.post",
        lambda *args, **kwargs: Response(),
    )
    client = ConfluenceClient(_settings(client_id="confluence-client", client_secret="super-secret"), _export())
    try:
        client._ensure_access_token()
    except RuntimeError as exc:
        message = str(exc)
    else:
        raise AssertionError("expected Atlassian to refuse the client")
    assert "super-secret" not in message
    assert "CONFLUENCE_OAUTH_CLIENT_ID" in message
    assert "credentials are wrong" in message


def _settings(**overrides) -> ConfluenceSettings:
    values = {
        "base_url": "https://acme.atlassian.net",
        "email": None,
        "api_token": None,
        "oauth_token": None,
        "space_key": "OPS",
        "parent_page_id": "555",
        "create_category_root": True,
        "root_page_title": None,
        "existing_title_policy": "fail",
        "upload_drafts": False,
        "restricted_article_policy": "warn",
        "oauth_client_id": overrides.get("client_id"),
        "oauth_client_secret": overrides.get("client_secret"),
    }
    if "email" in overrides:
        values["email"] = overrides["email"]
    if "api_token" in overrides:
        values["api_token"] = overrides["api_token"]
    return ConfluenceSettings(**values)


def _export() -> ExportSettings:
    return ExportSettings(
        output_dir=Path("output"),
        include_drafts=True,
        allow_partial_export=False,
        fail_on_unresolved_zendesk_links=False,
        request_timeout_seconds=30,
        article_limit=None,
    )
