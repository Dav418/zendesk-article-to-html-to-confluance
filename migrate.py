"""Download a Zendesk category and upload it to Confluence in batches.

Run this with start.command (Mac) or start.bat (Windows). It downloads the
category once, uploads the first 5 articles, asks you to look at them, then
uploads the rest 50 at a time.
"""

from __future__ import annotations

import logging
import sys
import traceback
from pathlib import Path

from zendesk_confluence_migrator.confluence_client import ConfluenceClient
from zendesk_confluence_migrator.confluence_uploader import ConfluenceUploader
from zendesk_confluence_migrator.exporter import KnowledgeBaseExporter
from zendesk_confluence_migrator.models import MigrationManifest, UploadState
from zendesk_confluence_migrator.selection import upload_batches
from zendesk_confluence_migrator.startup import (
    env_file_status,
    load_checked_config,
    placeholder_problems,
)
from zendesk_confluence_migrator.zendesk_client import ZendeskClient
from main import _find_workspace


FIRST_BATCH = 5
BATCH_SIZE = 50
CONTINUE_FLAG = "continue-upload.txt"
_RETRY_HINT = "Run the start script again after you save."


def _completed_count(workspace: Path) -> int:
    state_path = workspace / "confluence-upload-state.json"
    if not state_path.is_file():
        return 0
    return len(UploadState.load(state_path).completed_article_fingerprints)


def _root_url(workspace: Path) -> str | None:
    state_path = workspace / "confluence-upload-state.json"
    if not state_path.is_file():
        return None
    state = UploadState.load(state_path)
    if state.root is None:
        return None
    return state.root.url


def _ask_to_continue(root_url: str | None) -> bool:
    print()
    print("The first articles are now in Confluence.")
    if root_url:
        print(f"Open this page and check the articles under it:\n  {root_url}")
    else:
        print("Open the parent page you chose in Confluence and check the new articles.")
    print("Look at the text, images, and links.")
    print("Type yes to upload the rest. Type anything else to stop.")
    try:
        answer = input("> ").strip().casefold()
    except EOFError:
        return False
    return answer in {"y", "yes"}


def _write_error_log(workspace: Path | None, exc: BaseException) -> Path:
    folder = workspace if workspace is not None else Path("output")
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / "migration-error.log"
    path.write_text(traceback.format_exc(), encoding="utf-8")
    return path


def run() -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s",
        datefmt="%H:%M:%S",
    )
    print("This uploads a Zendesk help-center category into Confluence.")
    print("It downloads every article once, uploads 5 so you can check them,")
    print("then uploads the rest in groups of 50 if you type yes.")
    print()

    config = load_checked_config(
        require_confluence=True,
        require_zendesk_auth=True,
        retry_hint=_RETRY_HINT,
    )
    if config is None:
        return 1

    assert config.confluence is not None
    workspace: Path | None = None
    try:
        workspace, manifest = _load_or_export(config)
        if not manifest.export_ok:
            print("The Zendesk download did not finish cleanly, so nothing will be uploaded.")
            print(f"Look at {workspace / 'migration-report.json'} and run this again.")
            return 1

        uploader = ConfluenceUploader(
            config=config,
            client=ConfluenceClient(config.confluence, config.export),
            manifest=manifest,
            workspace_dir=workspace,
        )
        print("Checking Confluence before anything is created...")
        plan = uploader.preflight()
        if not plan.valid:
            print("Confluence check failed. No pages were created.")
            print(f"Look at {workspace / 'confluence-preflight.json'}")
            return 2

        batches = upload_batches(plan.articles_available, first=FIRST_BATCH, size=BATCH_SIZE)
        if not batches:
            print("There are no articles to upload.")
            return 0

        continue_flag = workspace / CONTINUE_FLAG
        completed = _completed_count(workspace)
        if continue_flag.is_file():
            remaining = [count for count in batches if count > completed]
            if not remaining:
                _print_finished(workspace)
                return 0
            print("Continuing the upload. Pages already created are kept.")
            print("Links in those pages are updated when they point at a page created in this batch.")
            _upload_counts(uploader, remaining, plan.articles_available)
            _print_finished(workspace)
            return 0

        preview = batches[0]
        print(f"Uploading the first {preview} of {plan.articles_available} articles...")
        uploader.upload(article_limit=preview)
        if len(batches) == 1:
            _print_finished(workspace)
            return 0

        if not _ask_to_continue(_root_url(workspace)):
            print()
            print("Stopped. The first articles are in Confluence and the rest were not uploaded.")
            print("Run this again when you want to continue.")
            return 0

        continue_flag.write_text("yes\n", encoding="utf-8")
        _upload_counts(uploader, batches[1:], plan.articles_available)
        _print_finished(workspace)
        return 0
    except KeyboardInterrupt:
        print()
        print("Stopped. Run this again to continue. Pages already created are kept.")
        return 130
    except Exception as exc:  # noqa: BLE001 - one plain message for the person running this
        log_path = _write_error_log(workspace, exc)
        print()
        print("The migration stopped.")
        print(exc)
        print("Pages already created are kept. Run this again to continue.")
        print(f"Technical details were saved to {log_path}")
        return 1


def _load_or_export(config: AppConfig) -> tuple[Path, MigrationManifest]:
    try:
        workspace, manifest = _find_workspace(config)
    except RuntimeError:
        workspace, manifest = None, None
    if workspace is not None and manifest is not None and manifest.export_ok:
        print(f"Using the Zendesk download already on this computer:\n  {workspace}")
        return workspace, manifest

    print("Downloading the Zendesk category. This can take a while.")
    zendesk = ZendeskClient(config.zendesk, config.export)
    KnowledgeBaseExporter(config=config, client=zendesk).run(article_limit=None)
    return _find_workspace(config)


def _upload_counts(uploader: ConfluenceUploader, counts: list[int], total: int) -> None:
    for count in counts:
        print()
        print(f"=== Uploading the first {count} of {total} articles ===")
        uploader.upload(article_limit=count)


def _print_finished(workspace: Path) -> None:
    print()
    print("Upload finished.")
    root = _root_url(workspace)
    if root:
        print(f"Open: {root}")
    print("Check the pages, images, and links in Confluence.")
    print("Then revoke the Zendesk and Confluence API tokens or OAuth clients you used for this.")


def main() -> int:
    return run()


if __name__ == "__main__":
    sys.exit(main())
