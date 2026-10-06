from __future__ import annotations

import logging
import shutil
from pathlib import Path

from zendesk_confluence_migrator.models import MigrationManifest


def workspace_is_usable(path: Path) -> bool:
    manifest_path = path / "manifest.json"
    if not manifest_path.is_file():
        return False
    try:
        return MigrationManifest.load(manifest_path).export_ok
    except (OSError, ValueError, KeyError, TypeError):
        return False


def recover_interrupted_export(final: Path) -> None:
    """Put a half-published export back into the folder upload expects."""
    previous = final.with_name(final.name + ".previous")
    staging = final.with_name(final.name + ".in-progress")
    if not final.exists() and workspace_is_usable(staging):
        staging.rename(final)
        logging.info("Finished saving an export that was interrupted while publishing.")
        if previous.exists():
            shutil.rmtree(previous)
        return
    if not final.exists() and previous.exists():
        previous.rename(final)
        logging.warning("Restored the previous export after an interrupted run.")
    if staging.exists():
        shutil.rmtree(staging)
    if previous.exists():
        shutil.rmtree(previous)


def publish_successful_export(staging: Path, final: Path, state_bytes: bytes | None) -> None:
    """Replace the current export only after the new one is complete."""
    previous = final.with_name(final.name + ".previous")
    if previous.exists():
        shutil.rmtree(previous)
    if final.exists():
        final.rename(previous)
    staging.rename(final)
    if state_bytes is not None:
        (final / "confluence-upload-state.json").write_bytes(state_bytes)
    if previous.exists():
        shutil.rmtree(previous)
