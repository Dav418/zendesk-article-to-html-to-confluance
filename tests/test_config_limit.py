from zendesk_confluence_migrator.config import AppConfig


def _zendesk_env(monkeypatch, tmp_path) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv(
        "ZENDESK_CATEGORY_URL",
        "https://company.zendesk.com/hc/en-gb/categories/123-name",
    )
    monkeypatch.setenv("ZENDESK_EMAIL", "person@example.com")
    monkeypatch.setenv("ZENDESK_API_TOKEN", "token")
    monkeypatch.delenv("ZENDESK_OAUTH_CLIENT_ID", raising=False)
    monkeypatch.delenv("ZENDESK_OAUTH_CLIENT_SECRET", raising=False)


def test_blank_article_limit_means_every_article(monkeypatch, tmp_path):
    _zendesk_env(monkeypatch, tmp_path)
    monkeypatch.setenv("ARTICLE_LIMIT", "  ")
    config = AppConfig.from_environment(require_confluence=False)
    assert config.export.article_limit is None


def test_article_limit_reads_a_positive_integer(monkeypatch, tmp_path):
    _zendesk_env(monkeypatch, tmp_path)
    monkeypatch.setenv("ARTICLE_LIMIT", "5")
    config = AppConfig.from_environment(require_confluence=False)
    assert config.export.article_limit == 5


def test_blank_email_names_that_line(monkeypatch, tmp_path):
    _zendesk_env(monkeypatch, tmp_path)
    monkeypatch.setenv("ZENDESK_EMAIL", "")
    try:
        AppConfig.from_environment(require_confluence=False)
    except ValueError as exc:
        message = str(exc)
    else:
        raise AssertionError("expected the blank email to be rejected")
    assert "ZENDESK_EMAIL is empty" in message
    assert "ZENDESK_API_TOKEN" not in message


def test_oauth_client_credentials_do_not_need_an_email(monkeypatch, tmp_path):
    _zendesk_env(monkeypatch, tmp_path)
    monkeypatch.setenv("ZENDESK_EMAIL", "")
    monkeypatch.setenv("ZENDESK_API_TOKEN", "")
    monkeypatch.setenv("ZENDESK_OAUTH_CLIENT_ID", "migration-client")
    monkeypatch.setenv("ZENDESK_OAUTH_CLIENT_SECRET", "migration-secret")
    config = AppConfig.from_environment(require_confluence=False)
    assert config.zendesk.oauth_client_id == "migration-client"
    assert config.zendesk.oauth_client_secret == "migration-secret"


def test_confluence_oauth_client_credentials_do_not_need_an_email(monkeypatch, tmp_path):
    _zendesk_env(monkeypatch, tmp_path)
    monkeypatch.setenv("CONFLUENCE_BASE_URL", "https://acme.atlassian.net/wiki")
    monkeypatch.setenv("CONFLUENCE_EMAIL", "")
    monkeypatch.setenv("CONFLUENCE_API_TOKEN", "")
    monkeypatch.setenv("CONFLUENCE_OAUTH_CLIENT_ID", "confluence-client")
    monkeypatch.setenv("CONFLUENCE_OAUTH_CLIENT_SECRET", "confluence-secret")
    monkeypatch.setenv("CONFLUENCE_SPACE_KEY", "OPS")
    monkeypatch.setenv("CONFLUENCE_PARENT_PAGE_ID", "555")
    config = AppConfig.from_environment(require_confluence=True)
    assert config.confluence is not None
    assert config.confluence.base_url == "https://acme.atlassian.net"
    assert config.confluence.oauth_client_id == "confluence-client"
    assert config.confluence.oauth_client_secret == "confluence-secret"


def test_article_limit_rejects_zero(monkeypatch, tmp_path):
    _zendesk_env(monkeypatch, tmp_path)
    monkeypatch.setenv("ARTICLE_LIMIT", "0")
    try:
        AppConfig.from_environment(require_confluence=False)
    except ValueError as exc:
        assert "ARTICLE_LIMIT" in str(exc)
    else:
        raise AssertionError("expected ARTICLE_LIMIT=0 to be rejected")
