"""Checks shared by the start scripts and by export, preflight, and upload."""

from __future__ import annotations

import os
import platform
import subprocess
import sys
from pathlib import Path

from dotenv import load_dotenv

from zendesk_confluence_migrator.config import AppConfig

_ZENDESK_SETTINGS = (
    ("ZENDESK_CATEGORY_URL", "Paste the browser address of the Zendesk category."),
)
_ZENDESK_LOGIN = (
    (
        "ZENDESK_EMAIL",
        "Put your Zendesk login email there. Leave the two OAuth client lines blank when you use this login.",
    ),
    (
        "ZENDESK_API_TOKEN",
        "Paste the Zendesk API token there. Only one Zendesk login is needed, not both.",
    ),
)
_CONFLUENCE_SETTINGS = (
    ("CONFLUENCE_BASE_URL", "Put your Confluence site address there, like https://company.atlassian.net"),
    ("CONFLUENCE_SPACE_KEY", "Put the space key there. It is the part after /spaces/ in the address."),
    ("CONFLUENCE_PARENT_PAGE_ID", "Put the number of the page to upload under there."),
)
_CONFLUENCE_LOGIN = (
    (
        "CONFLUENCE_EMAIL",
        "Put the email you use to log in to Confluence there. Leave the two OAuth client lines blank when you use this login.",
    ),
    (
        "CONFLUENCE_API_TOKEN",
        "Paste the Atlassian API token there. Only one Confluence login is needed, not both.",
    ),
)
_EXAMPLE_VALUES = {
    "ZENDESK_CATEGORY_URL": ("123456-category-name", "//company.zendesk.com"),
    "ZENDESK_EMAIL": ("you@company.com",),
    "ZENDESK_API_TOKEN": ("PASTE_",),
    "CONFLUENCE_BASE_URL": ("//company.atlassian.net",),
    "CONFLUENCE_EMAIL": ("you@company.com",),
    "CONFLUENCE_API_TOKEN": ("PASTE_",),
    "CONFLUENCE_PARENT_PAGE_ID": ("123456789",),
}


def env_problems(*, require_confluence: bool) -> list[str]:
    """List every needed .env line that is empty or still has the example value."""
    problems = _setting_problems(_ZENDESK_SETTINGS)
    problems.extend(_zendesk_login_problems())
    if require_confluence:
        problems.extend(_setting_problems(_CONFLUENCE_SETTINGS))
        problems.extend(_confluence_login_problems())
    return problems


def _confluence_login_problems() -> list[str]:
    """OAuth client ID + secret, or email + API token."""
    if _value("CONFLUENCE_OAUTH_CLIENT_ID") or _value("CONFLUENCE_OAUTH_CLIENT_SECRET"):
        return _setting_problems(
            (
                (
                    "CONFLUENCE_OAUTH_CLIENT_ID",
                    "Put the OAuth client ID there. Leave the email and API token blank when you use this login.",
                ),
                (
                    "CONFLUENCE_OAUTH_CLIENT_SECRET",
                    "Put the OAuth client secret there. Only one Confluence login is needed, not both.",
                ),
            )
        )
    return _setting_problems(_CONFLUENCE_LOGIN)


def _zendesk_login_problems() -> list[str]:
    """OAuth client Identifier + Secret, or email + API token."""
    if _value("ZENDESK_OAUTH_CLIENT_ID") or _value("ZENDESK_OAUTH_CLIENT_SECRET"):
        return _setting_problems(
            (
                (
                    "ZENDESK_OAUTH_CLIENT_ID",
                    "Put the OAuth client Identifier there. Leave the email and API token blank when you use this login.",
                ),
                (
                    "ZENDESK_OAUTH_CLIENT_SECRET",
                    "Put the OAuth client Secret there. Only one Zendesk login is needed, not both.",
                ),
            )
        )
    return _setting_problems(_ZENDESK_LOGIN)


def _setting_problems(settings: tuple[tuple[str, str], ...]) -> list[str]:
    problems: list[str] = []
    for name, hint in settings:
        value = _value(name)
        if not value:
            problems.append(f"{name} is empty. {hint}")
        elif _is_example(name, value):
            problems.append(f"{name} still has the example value. {hint}")
    return problems


def _value(name: str) -> str:
    return os.getenv(name, "").strip()


def _is_example(name: str, value: str) -> bool:
    if name == "CONFLUENCE_PARENT_PAGE_ID":
        return value == "123456789"
    return any(marker in value for marker in _EXAMPLE_VALUES.get(name, ()))


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
    print("Zendesk needs one login, and Confluence needs one login.")
    print("For each, fill in either the email and API token, or the OAuth client ID and secret.")
    print("Leave the other login blank. Example text such as PASTE_ZENDESK_TOKEN_HERE is not enough.")
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

    uses_client_credentials = bool(
        config.zendesk.oauth_client_id and config.zendesk.oauth_client_secret
    )
    if "123456-category-name" in config.zendesk.category_url:
        problems.append("ZENDESK_CATEGORY_URL is still the example. Paste your category URL.")
    if not uses_client_credentials and config.zendesk.email == "you@company.com":
        problems.append("ZENDESK_EMAIL is still you@company.com.")
    if not uses_client_credentials and _is_placeholder(config.zendesk.api_token):
        problems.append("ZENDESK_API_TOKEN is still the example. Paste the Zendesk token.")

    uses_confluence_client = bool(confluence.oauth_client_id and confluence.oauth_client_secret)
    if not uses_confluence_client and confluence.email == "you@company.com":
        problems.append("CONFLUENCE_EMAIL is still you@company.com.")
    if not uses_confluence_client and _is_placeholder(confluence.api_token):
        problems.append("CONFLUENCE_API_TOKEN is still the example. Paste the Atlassian token.")
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

    load_dotenv(env_path)
    problems = env_problems(require_confluence=require_confluence)
    if problems:
        print("These lines in .env need filling in:")
        for problem in problems:
            print(f"  - {problem}")
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
