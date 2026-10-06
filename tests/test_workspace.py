import json
from pathlib import Path

from zendesk_confluence_migrator.workspace import (
    publish_successful_export,
    recover_interrupted_export,
    workspace_is_usable,
)


def _write_manifest(directory: Path, *, export_ok: bool) -> None:
    directory.mkdir(parents=True)
    payload = {
        "schema_version": 1,
        "generated_at_utc": "2026-10-06T00:00:00+00:00",
        "zendesk_origin": "https://company.zendesk.com",
        "zendesk_host": "company.zendesk.com",
        "locale": "en-gb",
        "category_id": 1,
        "category_name": "Knowledge",
        "category_description_html": "",
        "category_source_url": "https://company.zendesk.com/hc/en-gb/categories/1",
        "html_space_folder": "Knowledge",
        "sections": [],
        "articles": [],
        "export_ok": export_ok,
    }
    (directory / "manifest.json").write_text(json.dumps(payload), encoding="utf-8")


def test_publish_replaces_the_old_export_and_keeps_upload_state(tmp_path: Path):
    final = tmp_path / "zendesk-category-1"
    _write_manifest(final, export_ok=True)
    (final / "confluence-upload-state.json").write_text('{"keep": true}', encoding="utf-8")
    (final / "old.txt").write_text("old", encoding="utf-8")

    staging = tmp_path / "zendesk-category-1.in-progress"
    _write_manifest(staging, export_ok=True)
    (staging / "new.txt").write_text("new", encoding="utf-8")

    publish_successful_export(staging, final, b'{"keep": true}')

    assert (final / "new.txt").read_text(encoding="utf-8") == "new"
    assert not (final / "old.txt").exists()
    assert json.loads((final / "confluence-upload-state.json").read_text(encoding="utf-8")) == {
        "keep": True
    }
    assert not staging.exists()
    assert not (tmp_path / "zendesk-category-1.previous").exists()
    assert workspace_is_usable(final)


def test_recover_promotes_a_finished_staging_folder(tmp_path: Path):
    final = tmp_path / "zendesk-category-1"
    previous = tmp_path / "zendesk-category-1.previous"
    staging = tmp_path / "zendesk-category-1.in-progress"
    _write_manifest(previous, export_ok=True)
    _write_manifest(staging, export_ok=True)
    (staging / "finished.txt").write_text("yes", encoding="utf-8")

    recover_interrupted_export(final)

    assert (final / "finished.txt").read_text(encoding="utf-8") == "yes"
    assert not staging.exists()
    assert not previous.exists()


def test_recover_restores_the_previous_export_when_staging_is_incomplete(tmp_path: Path):
    final = tmp_path / "zendesk-category-1"
    previous = tmp_path / "zendesk-category-1.previous"
    staging = tmp_path / "zendesk-category-1.in-progress"
    _write_manifest(previous, export_ok=True)
    (previous / "kept.txt").write_text("kept", encoding="utf-8")
    staging.mkdir()
    (staging / "partial.txt").write_text("partial", encoding="utf-8")

    recover_interrupted_export(final)

    assert (final / "kept.txt").read_text(encoding="utf-8") == "kept"
    assert not staging.exists()
    assert not previous.exists()
