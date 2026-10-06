from pathlib import Path

import pytest

from zendesk_confluence_migrator.config import (
    AppConfig,
    ConfluenceSettings,
    ExportSettings,
    ZendeskSettings,
)
from zendesk_confluence_migrator.confluence_uploader import (
    ConfluenceUploader,
    article_content_fingerprint,
)
from zendesk_confluence_migrator.models import (
    ArticleRecord,
    ConfluencePageState,
    MigrationManifest,
    SectionRecord,
    UploadState,
)


class _FakeConfluence:
    def __init__(self, pages: list[dict] | None = None) -> None:
        self._pages = pages or [{"id": "1", "title": "Parent"}]

    def get_space(self, space_key: str) -> dict:
        return {"key": space_key}

    def get_page(self, page_id: str) -> dict:
        return {
            "id": page_id,
            "title": "Parent",
            "space": {"key": "OPS"},
            "version": {"number": 1},
        }

    def list_pages_in_space(self, space_key: str) -> list[dict]:
        return list(self._pages)

    def page_url(self, page: dict, *, space_key: str | None = None) -> str:
        return f"https://company.atlassian.net/wiki/pages/{page.get('id')}"


def _article(
    article_id: int,
    *,
    title: str,
    section_id: int,
    position: int,
    draft: bool = False,
) -> ArticleRecord:
    return ArticleRecord(
        id=article_id,
        title=title,
        body_html="<p>Body</p>",
        source_url=None,
        section_id=section_id,
        position=position,
        draft=draft,
        restricted=False,
        page_stem=title,
        export_file=f"{title}.html",
    )


def _manifest(*, export_ok: bool = True) -> MigrationManifest:
    return MigrationManifest(
        schema_version=1,
        generated_at_utc="2026-10-06T00:00:00+00:00",
        zendesk_origin="https://company.zendesk.com",
        zendesk_host="company.zendesk.com",
        locale="en-gb",
        category_id=100,
        category_name="Knowledge",
        category_description_html="",
        category_source_url="https://company.zendesk.com/hc/en-gb/categories/100-knowledge",
        html_space_folder="Knowledge",
        sections=[
            SectionRecord(30, "Topic", "", None, None, 0),
            SectionRecord(20, "Guides", "", None, 30, 0),
            SectionRecord(10, "Other", "", None, None, 5),
        ],
        articles=[
            _article(4, title="Draft first", section_id=20, position=0, draft=True),
            _article(2, title="Shared", section_id=20, position=1),
            _article(1, title="Shared", section_id=10, position=0),
        ],
        export_ok=export_ok,
    )


def _config() -> AppConfig:
    return AppConfig(
        zendesk=ZendeskSettings(
            category_url="https://company.zendesk.com/hc/en-gb/categories/100-knowledge",
            origin="https://company.zendesk.com",
            host="company.zendesk.com",
            locale="en-gb",
            category_id=100,
            email=None,
            api_token=None,
            oauth_token=None,
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
            email=None,
            api_token=None,
            oauth_token="token",
            space_key="OPS",
            parent_page_id="1",
            create_category_root=True,
            root_page_title=None,
            existing_title_policy="fail",
            upload_drafts=False,
            restricted_article_policy="warn",
        ),
    )


def _uploader(
    tmp_path: Path,
    client: _FakeConfluence | None = None,
    *,
    export_ok: bool = True,
) -> ConfluenceUploader:
    return ConfluenceUploader(
        config=_config(),
        client=client or _FakeConfluence(),
        manifest=_manifest(export_ok=export_ok),
        workspace_dir=tmp_path,
    )


def test_preflight_refuses_a_failed_export(tmp_path: Path):
    with pytest.raises(RuntimeError, match="did not finish cleanly"):
        _uploader(tmp_path, export_ok=False).preflight()


def test_article_fingerprint_changes_when_the_body_changes():
    article = _article(2, title="Shared", section_id=20, position=1)
    changed = ArticleRecord(
        id=article.id,
        title=article.title,
        body_html="<p>Changed</p>",
        source_url=article.source_url,
        section_id=article.section_id,
        position=article.position,
        draft=article.draft,
        restricted=article.restricted,
        page_stem=article.page_stem,
        export_file=article.export_file,
    )
    assert article_content_fingerprint(article) == article_content_fingerprint(article)
    assert article_content_fingerprint(article) != article_content_fingerprint(changed)


def test_preflight_limit_skips_drafts_and_unrelated_sections(tmp_path: Path):
    plan = _uploader(tmp_path).preflight(article_limit=1)

    assert plan.valid
    assert plan.articles_available == 2
    assert plan.drafts_skipped == 1
    assert set(plan.article_titles) == {2}
    assert plan.article_titles[2] == "Shared"
    assert set(plan.section_titles) == {30, 20}


def test_preflight_limit_reuses_titles_from_an_earlier_batch(tmp_path: Path):
    state = UploadState(
        schema_version=1,
        category_id=100,
        confluence_base_url="https://company.atlassian.net",
        confluence_space_key="OPS",
        configured_parent_page_id="1",
        create_category_root=True,
        articles={
            1: ConfluencePageState(
                page_id="99",
                title="Shared",
                url="https://company.atlassian.net/wiki/pages/99",
            )
        },
    )
    state.save(tmp_path / "confluence-upload-state.json")
    client = _FakeConfluence(
        pages=[
            {"id": "1", "title": "Parent"},
            {"id": "99", "title": "Shared"},
        ]
    )

    plan = _uploader(tmp_path, client).preflight(article_limit=1)

    assert plan.valid
    assert set(plan.article_titles) == {2}
    assert plan.article_titles[2] == "Shared (Zendesk article-2)"
    assert any("outside this batch" in warning for warning in plan.warnings)


def test_preflight_without_a_limit_includes_every_uploadable_article(tmp_path: Path):
    plan = _uploader(tmp_path).preflight()

    assert plan.valid
    assert set(plan.article_titles) == {1, 2}
    assert set(plan.section_titles) == {30, 20, 10}
    assert plan.article_limit is None
