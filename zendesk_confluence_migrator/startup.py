"""Checks shared by the start scripts and by export, preflight, and upload."""

from __future__ import annotations

import platform
import subprocess
import sys
from pathlib import Path

from zendesk_confluence_migrator.config import AppConfig


def ensure_python() -> bool:
    """Stop with install instructions when this command is not on Python 3.11+."""
    if sys.version_info >= (3, 11):
        return True
    found = (
        f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    )
    print(f"Python 3.11 or newer is required. This command is using Python {found}.")
    system = platform.system()
    if system == "Windows":
        print("Install it from https://www.python.org/downloads/windows/")
        print('During setup, tick "Add python.exe to PATH".')
        print("Close this window, open a new Command Prompt, and run: py -3 --version")
    elif system == "Darwin":
        print("Install it from https://www.python.org/downloads/macos/")
        print("Close Terminal, open it again, and run: python3 --version")
    else:
        print("Install Python 3.11 or newer from https://www.python.org/downloads/")
    return False


def env_file_status(env_path: Path) -> str:
    """Return ``missing``, ``empty``, or ``present``."""
    if not env_path.is_file():
        return "missing"
    text = env_path.read_text(encoding="utf-8")
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        if stripped.split("=", 1)[1].strip():
            return "present"
    return "empty"


def explain_env_file(env_path: Path, *, retry_hint: str) -> None:
    """Tell the person where .env is and open it. The name starts with a dot, so Finder hides it."""
    print()
    print("The migration cannot start until .env has your real Zendesk and Confluence values.")
    print("Example text such as PASTE_ZENDESK_TOKEN_HERE or an empty file is not enough.")
    print(f"The file is here:\n  {env_path}")
    print("It is in the same folder as start.command and start.bat. It is not inside .venv.")
    print()
    if platform.system() == "Windows":
        print("If you cannot see .env in File Explorer:")
        print("  1. Open the unzipped folder, the one that contains start.bat.")
        print("  2. Click the View menu, then Show.")
        print("  3. Tick File name extensions.")
        print("  4. Tick Hidden items.")
        print("Notepad should open .env now. Replace the example values, then use File, Save.")
    else:
        print("If you cannot see .env in Finder, that is normal. A file whose name starts with")
        print("a dot is hidden.")
        print("  1. Open the unzipped folder in Finder, the one that contains start.command.")
        print("  2. Press Command + Shift + . (the period key). Hidden files appear in grey.")
        print("  3. Double-click .env. If Mac asks for an app, choose TextEdit.")
        print("  4. Press Command + Shift + . again when you want to hide those files.")
        print("Do not edit the .venv folder. That is a different hidden item.")
        print("TextEdit should open .env now. Replace the example values, then save.")
    print(retry_hint)
    _open_env_file(env_path)


def _open_env_file(env_path: Path) -> None:
    try:
        if platform.system() == "Windows":
            subprocess.Popen(["notepad", str(env_path)])
        elif platform.system() == "Darwin":
            subprocess.run(["open", "-e", str(env_path)], check=False)
        else:
            subprocess.run(["xdg-open", str(env_path)], check=False)
    except OSError:
        print("The file could not be opened automatically. Open the path printed above.")


def placeholder_problems(config: AppConfig) -> list[str]:
    """Return plain-language problems when .env still has the sample values."""
    problems: list[str] = []
    confluence = config.confluence
    if confluence is None:
        return ["Confluence settings are missing from .env"]

    if "123456-category-name" in config.zendesk.category_url:
        problems.append("ZENDESK_CATEGORY_URL is still the example. Paste your category URL.")
    if not config.zendesk.oauth_token and config.zendesk.email == "you@company.com":
        problems.append("ZENDESK_EMAIL is still you@company.com.")
    if not config.zendesk.oauth_token and _is_placeholder(config.zendesk.api_token):
        problems.append("ZENDESK_API_TOKEN is still the example. Paste the Zendesk token.")
    if _is_placeholder(config.zendesk.oauth_token):
        problems.append("ZENDESK_OAUTH_TOKEN is still the example.")

    if not confluence.oauth_token and confluence.email == "you@company.com":
        problems.append("CONFLUENCE_EMAIL is still you@company.com.")
    if not confluence.oauth_token and _is_placeholder(confluence.api_token):
        problems.append("CONFLUENCE_API_TOKEN is still the example. Paste the Atlassian token.")
    if _is_placeholder(confluence.oauth_token):
        problems.append("CONFLUENCE_OAUTH_TOKEN is still the example.")
    if confluence.parent_page_id == "123456789":
        problems.append("CONFLUENCE_PARENT_PAGE_ID is still 123456789. Paste the real page ID.")
    return problems


def _is_placeholder(value: str | None) -> bool:
    return bool(value and "PASTE_" in value)


def load_checked_config(
    *,
    require_confluence: bool,
    require_zendesk_auth: bool,
    retry_hint: str,
) -> AppConfig | None:
    """Return config, or None after printing how to fix Python or .env."""
    if not ensure_python():
        return None

    env_path = Path.cwd() / ".env"
    example_path = Path.cwd() / ".env.example"
    status = env_file_status(env_path)
    if status in {"missing", "empty"}:
        if example_path.is_file():
            env_path.write_text(example_path.read_text(encoding="utf-8"), encoding="utf-8")
            print("Created .env from .env.example. The new file still contains example values.")
        elif status == "missing":
            print("There is no .env file in this folder, and .env.example is missing too.")
            return None
        else:
            print(".env is empty. Fill in your Zendesk and Confluence values.")
        explain_env_file(env_path, retry_hint=retry_hint)
        return None

    try:
        config = AppConfig.from_environment(
            require_confluence=require_confluence,
            require_zendesk_auth=require_zendesk_auth,
        )
    except ValueError as exc:
        print(exc)
        explain_env_file(env_path, retry_hint=retry_hint)
        return None

    problems = placeholder_problems(config)
    if problems:
        print("Edit .env before continuing:")
        for problem in problems:
            print(f"  - {problem}")
        explain_env_file(env_path, retry_hint=retry_hint)
        return None
    return config
