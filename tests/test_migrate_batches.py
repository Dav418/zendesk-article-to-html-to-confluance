from zendesk_confluence_migrator.config import AppConfig, ConfluenceSettings, ExportSettings, ZendeskSettings
from zendesk_confluence_migrator.selection import upload_batches
from zendesk_confluence_migrator.startup import env_problems, load_checked_config
from migrate import env_file_status, placeholder_problems
from pathlib import Path


_ENV_KEYS = (
    "ZENDESK_CATEGORY_URL",
    "ZENDESK_OAUTH_CLIENT_ID",
    "ZENDESK_OAUTH_CLIENT_SECRET",
    "ZENDESK_EMAIL",
    "ZENDESK_API_TOKEN",
    "CONFLUENCE_BASE_URL",
    "CONFLUENCE_EMAIL",
    "CONFLUENCE_API_TOKEN",
    "CONFLUENCE_OAUTH_CLIENT_ID",
    "CONFLUENCE_OAUTH_CLIENT_SECRET",
    "CONFLUENCE_SPACE_KEY",
    "CONFLUENCE_PARENT_PAGE_ID",
    "ARTICLE_LIMIT",
)


def test_upload_batches_preview_then_groups_of_50():
    assert upload_batches(3) == [3]
    assert upload_batches(5) == [5]
    assert upload_batches(40) == [5, 40]
    assert upload_batches(120) == [5, 50, 100, 120]
    assert upload_batches(400) == [5, 50, 100, 150, 200, 250, 300, 350, 400]


def test_env_file_status_treats_a_blank_file_as_empty(tmp_path: Path):
    missing = tmp_path / ".env"
    assert env_file_status(missing) == "missing"
    missing.write_text("\n\n# nothing here\nZENDESK_EMAIL=\n", encoding="utf-8")
    assert env_file_status(missing) == "empty"
    missing.write_text("ZENDESK_EMAIL=person@acme.com\n", encoding="utf-8")
    assert env_file_status(missing) == "present"


def test_placeholder_problems_flags_the_sample_env():
    problems = placeholder_problems(_config())
    assert any("ZENDESK_CATEGORY_URL" in problem for problem in problems)
    assert any("ZENDESK_API_TOKEN" in problem for problem in problems)
    assert any("CONFLUENCE_PARENT_PAGE_ID" in problem for problem in problems)


def test_load_checked_config_stops_on_the_example_env(tmp_path: Path, monkeypatch):
    example = Path(".env.example").read_text(encoding="utf-8")
    (tmp_path / ".env.example").write_text(example, encoding="utf-8")
    (tmp_path / ".env").write_text(example, encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    for key in _ENV_KEYS:
        monkeypatch.delenv(key, raising=False)
    opened: list[Path] = []
    monkeypatch.setattr(
        "zendesk_confluence_migrator.startup._open_env_file",
        lambda path: opened.append(path),
    )

    result = load_checked_config(
        require_confluence=True,
        require_zendesk_auth=True,
        retry_hint="Run the same command again after you save .env.",
    )

    assert result is None
    assert opened == [tmp_path / ".env"]


def test_env_problems_lists_every_empty_line(monkeypatch):
    for key in _ENV_KEYS:
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("ZENDESK_CATEGORY_URL", "https://acme.zendesk.com/hc/en-gb/categories/999-help")
    monkeypatch.setenv("ZENDESK_API_TOKEN", "real-zendesk-token")
    monkeypatch.setenv("CONFLUENCE_PARENT_PAGE_ID", "123456789")

    problems = env_problems(require_confluence=True)
    names = [problem.split(" ", 1)[0] for problem in problems]

    assert names == [
        "ZENDESK_EMAIL",
        "CONFLUENCE_BASE_URL",
        "CONFLUENCE_SPACE_KEY",
        "CONFLUENCE_PARENT_PAGE_ID",
        "CONFLUENCE_EMAIL",
        "CONFLUENCE_API_TOKEN",
    ]
    assert "example value" in problems[3]


def test_one_finished_login_does_not_require_the_other(monkeypatch):
    for key in _ENV_KEYS:
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("ZENDESK_CATEGORY_URL", "https://acme.zendesk.com/hc/en-gb/categories/999-help")
    monkeypatch.setenv("ZENDESK_EMAIL", "person@acme.com")
    monkeypatch.setenv("ZENDESK_API_TOKEN", "zendesk-token")
    monkeypatch.setenv("CONFLUENCE_BASE_URL", "https://acme.atlassian.net")
    monkeypatch.setenv("CONFLUENCE_OAUTH_CLIENT_ID", "confluence-client")
    monkeypatch.setenv("CONFLUENCE_OAUTH_CLIENT_SECRET", "confluence-secret")
    monkeypatch.setenv("CONFLUENCE_SPACE_KEY", "OPS")
    monkeypatch.setenv("CONFLUENCE_PARENT_PAGE_ID", "555")

    assert env_problems(require_confluence=True) == []


def test_oauth_client_credentials_replace_the_email_login(monkeypatch):
    for key in _ENV_KEYS:
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("ZENDESK_CATEGORY_URL", "https://acme.zendesk.com/hc/en-gb/categories/999-help")
    monkeypatch.setenv("ZENDESK_OAUTH_CLIENT_ID", "migration-client")
    monkeypatch.setenv("CONFLUENCE_BASE_URL", "https://acme.atlassian.net")
    monkeypatch.setenv("CONFLUENCE_EMAIL", "person@acme.com")
    monkeypatch.setenv("CONFLUENCE_API_TOKEN", "atlas-token")
    monkeypatch.setenv("CONFLUENCE_SPACE_KEY", "OPS")
    monkeypatch.setenv("CONFLUENCE_PARENT_PAGE_ID", "555")

    names = [problem.split(" ", 1)[0] for problem in env_problems(require_confluence=True)]

    assert names == ["ZENDESK_OAUTH_CLIENT_SECRET"]


def test_confluence_oauth_client_replaces_the_email_login(monkeypatch):
    for key in _ENV_KEYS:
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("ZENDESK_CATEGORY_URL", "https://acme.zendesk.com/hc/en-gb/categories/999-help")
    monkeypatch.setenv("ZENDESK_EMAIL", "person@acme.com")
    monkeypatch.setenv("ZENDESK_API_TOKEN", "zendesk-token")
    monkeypatch.setenv("CONFLUENCE_BASE_URL", "https://acme.atlassian.net")
    monkeypatch.setenv("CONFLUENCE_OAUTH_CLIENT_ID", "confluence-client")
    monkeypatch.setenv("CONFLUENCE_SPACE_KEY", "OPS")
    monkeypatch.setenv("CONFLUENCE_PARENT_PAGE_ID", "555")

    names = [problem.split(" ", 1)[0] for problem in env_problems(require_confluence=True)]

    assert names == ["CONFLUENCE_OAUTH_CLIENT_SECRET"]


def test_placeholder_problems_accepts_real_values():
    config = _config()
    zendesk = config.zendesk
    confluence = config.confluence
    assert confluence is not None
    real = AppConfig(
        zendesk=ZendeskSettings(
            category_url="https://acme.zendesk.com/hc/en-gb/categories/999-help",
            origin=zendesk.origin,
            host=zendesk.host,
            locale=zendesk.locale,
            category_id=999,
            email="person@acme.com",
            api_token="real-zendesk-token",
        ),
        export=config.export,
        confluence=ConfluenceSettings(
            base_url=confluence.base_url,
            email="person@acme.com",
            api_token="real-atlassian-token",
            space_key="OPS",
            parent_page_id="555",
            create_category_root=True,
            root_page_title=None,
            existing_title_policy="fail",
            upload_drafts=False,
            restricted_article_policy="warn",
        ),
    )
    assert placeholder_problems(real) == []


def _config() -> AppConfig:
    return AppConfig(
        zendesk=ZendeskSettings(
            category_url="https://company.zendesk.com/hc/en-gb/categories/123456-category-name",
            origin="https://company.zendesk.com",
            host="company.zendesk.com",
            locale="en-gb",
            category_id=123456,
            email="you@company.com",
            api_token="PASTE_ZENDESK_TOKEN_HERE",
        ),
        export=ExportSettings(
            output_dir=Path("output"),
            include_drafts=True,
            allow_partial_export=False,
            fail_on_unresolved_zendesk_links=False,
            request_timeout_seconds=30,
            article_limit=None,
        ),
        confluence=ConfluenceSettings(
            base_url="https://company.atlassian.net",
            email="you@company.com",
            api_token="PASTE_ATLASSIAN_TOKEN_HERE",
            space_key="OPS",
            parent_page_id="123456789",
            create_category_root=True,
            root_page_title=None,
            existing_title_policy="fail",
            upload_drafts=False,
            restricted_article_policy="warn",
        ),
    )
