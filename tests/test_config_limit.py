from zendesk_confluence_migrator.config import AppConfig


def _zendesk_env(monkeypatch, tmp_path) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv(
        "ZENDESK_CATEGORY_URL",
        "https://company.zendesk.com/hc/en-gb/categories/123-name",
    )
    monkeypatch.setenv("ZENDESK_EMAIL", "person@example.com")
    monkeypatch.setenv("ZENDESK_API_TOKEN", "token")
    monkeypatch.delenv("ZENDESK_OAUTH_TOKEN", raising=False)


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


def test_article_limit_rejects_zero(monkeypatch, tmp_path):
    _zendesk_env(monkeypatch, tmp_path)
    monkeypatch.setenv("ARTICLE_LIMIT", "0")
    try:
        AppConfig.from_environment(require_confluence=False)
    except ValueError as exc:
        assert "ARTICLE_LIMIT" in str(exc)
    else:
        raise AssertionError("expected ARTICLE_LIMIT=0 to be rejected")
