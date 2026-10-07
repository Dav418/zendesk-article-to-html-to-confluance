from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

from dotenv import load_dotenv


_CATEGORY_PATH_RE = re.compile(
    r"^/hc/(?P<locale>[^/]+)/categories/(?P<category_id>\d+)(?:-[^/?#]*)?/?$",
    re.IGNORECASE,
)


def _parse_bool(value: str | None, default: bool) -> bool:
    if value is None or value.strip() == "":
        return default
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "y", "on"}:
        return True
    if normalized in {"0", "false", "no", "n", "off"}:
        return False
    raise ValueError(f"Invalid boolean value: {value!r}")


def _required(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise ValueError(f"{name} is empty in .env.")
    return value


def _require_login(*, email_name: str, email_hint: str, token_name: str, token_hint: str, oauth_name: str) -> None:
    """Fail with the exact empty lines when email+token login is incomplete."""
    if os.getenv(oauth_name, "").strip():
        return
    missing: list[str] = []
    if not os.getenv(email_name, "").strip():
        missing.append(f"{email_name} is empty. {email_hint}")
    if not os.getenv(token_name, "").strip():
        missing.append(f"{token_name} is empty. {token_hint}")
    if missing:
        raise ValueError("\n".join(missing))


def _optional_positive_int(name: str) -> int | None:
    raw = os.getenv(name, "").strip()
    if not raw:
        return None
    try:
        value = int(raw)
    except ValueError as exc:
        raise ValueError(f"{name} must be a positive integer") from exc
    if value <= 0:
        raise ValueError(f"{name} must be a positive integer")
    return value


@dataclass(frozen=True)
class ZendeskSettings:
    category_url: str
    origin: str
    host: str
    locale: str
    category_id: int
    email: str | None
    api_token: str | None
    oauth_token: str | None


@dataclass(frozen=True)
class ExportSettings:
    output_dir: Path
    include_drafts: bool
    allow_partial_export: bool
    fail_on_unresolved_zendesk_links: bool
    request_timeout_seconds: int
    article_limit: int | None


@dataclass(frozen=True)
class ConfluenceSettings:
    base_url: str
    email: str | None
    api_token: str | None
    oauth_token: str | None
    space_key: str
    parent_page_id: str
    create_category_root: bool
    root_page_title: str | None
    existing_title_policy: str
    upload_drafts: bool
    restricted_article_policy: str


@dataclass(frozen=True)
class AppConfig:
    zendesk: ZendeskSettings
    export: ExportSettings
    confluence: ConfluenceSettings | None

    @classmethod
    def from_environment(
        cls, *, require_confluence: bool, require_zendesk_auth: bool = True
    ) -> "AppConfig":
        load_dotenv()

        category_url = _required("ZENDESK_CATEGORY_URL")
        parsed = urlparse(category_url)
        if parsed.scheme not in {"https", "http"} or not parsed.hostname:
            raise ValueError("ZENDESK_CATEGORY_URL must be a full http(s) URL")
        match = _CATEGORY_PATH_RE.match(parsed.path)
        if not match:
            raise ValueError(
                "ZENDESK_CATEGORY_URL must look like "
                "https://company.zendesk.com/hc/en-gb/categories/123456-category-name"
            )

        zendesk_oauth = os.getenv("ZENDESK_OAUTH_TOKEN", "").strip() or None
        zendesk_email = os.getenv("ZENDESK_EMAIL", "").strip() or None
        zendesk_api_token = os.getenv("ZENDESK_API_TOKEN", "").strip() or None
        if require_zendesk_auth:
            _require_login(
                email_name="ZENDESK_EMAIL",
                email_hint="Put your Zendesk login email on that line.",
                token_name="ZENDESK_API_TOKEN",
                token_hint="Put the Zendesk API token on that line.",
                oauth_name="ZENDESK_OAUTH_TOKEN",
            )

        timeout_raw = os.getenv("REQUEST_TIMEOUT_SECONDS", "30").strip()
        try:
            timeout = int(timeout_raw)
        except ValueError as exc:
            raise ValueError("REQUEST_TIMEOUT_SECONDS must be an integer") from exc
        if timeout <= 0:
            raise ValueError("REQUEST_TIMEOUT_SECONDS must be greater than zero")

        zendesk = ZendeskSettings(
            category_url=category_url,
            origin=f"{parsed.scheme}://{parsed.netloc}",
            host=parsed.hostname.lower(),
            locale=match.group("locale"),
            category_id=int(match.group("category_id")),
            email=zendesk_email,
            api_token=zendesk_api_token,
            oauth_token=zendesk_oauth,
        )
        export = ExportSettings(
            output_dir=Path(os.getenv("OUTPUT_DIR", "output").strip() or "output"),
            include_drafts=_parse_bool(os.getenv("INCLUDE_DRAFTS"), True),
            allow_partial_export=_parse_bool(os.getenv("ALLOW_PARTIAL_EXPORT"), False),
            fail_on_unresolved_zendesk_links=_parse_bool(
                os.getenv("FAIL_ON_UNRESOLVED_ZENDESK_LINKS"), False
            ),
            request_timeout_seconds=timeout,
            article_limit=_optional_positive_int("ARTICLE_LIMIT"),
        )

        confluence = None
        if require_confluence:
            base_url_raw = _required("CONFLUENCE_BASE_URL")
            base_parsed = urlparse(base_url_raw)
            if base_parsed.scheme != "https" or not base_parsed.hostname:
                raise ValueError("CONFLUENCE_BASE_URL must be a full https URL")
            base_path = base_parsed.path.rstrip("/")
            if base_path.endswith("/wiki"):
                base_path = base_path[:-5]
            base_url = f"{base_parsed.scheme}://{base_parsed.netloc}{base_path}".rstrip("/")

            confluence_oauth = os.getenv("CONFLUENCE_OAUTH_TOKEN", "").strip() or None
            confluence_email = os.getenv("CONFLUENCE_EMAIL", "").strip() or None
            confluence_api_token = os.getenv("CONFLUENCE_API_TOKEN", "").strip() or None
            _require_login(
                email_name="CONFLUENCE_EMAIL",
                email_hint="Put the email you use to log in to Confluence on that line.",
                token_name="CONFLUENCE_API_TOKEN",
                token_hint="Put the Atlassian API token on that line.",
                oauth_name="CONFLUENCE_OAUTH_TOKEN",
            )

            title_policy = os.getenv("CONFLUENCE_EXISTING_TITLE_POLICY", "fail").strip().lower()
            if title_policy not in {"fail", "suffix"}:
                raise ValueError(
                    "CONFLUENCE_EXISTING_TITLE_POLICY must be either 'fail' or 'suffix'"
                )
            restricted_policy = os.getenv(
                "CONFLUENCE_RESTRICTED_ARTICLE_POLICY", "warn"
            ).strip().lower()
            if restricted_policy not in {"warn", "fail"}:
                raise ValueError(
                    "CONFLUENCE_RESTRICTED_ARTICLE_POLICY must be either 'warn' or 'fail'"
                )

            confluence = ConfluenceSettings(
                base_url=base_url,
                email=confluence_email,
                api_token=confluence_api_token,
                oauth_token=confluence_oauth,
                space_key=_required("CONFLUENCE_SPACE_KEY"),
                parent_page_id=_required("CONFLUENCE_PARENT_PAGE_ID"),
                create_category_root=_parse_bool(
                    os.getenv("CONFLUENCE_CREATE_CATEGORY_ROOT"), True
                ),
                root_page_title=os.getenv("CONFLUENCE_ROOT_PAGE_TITLE", "").strip() or None,
                existing_title_policy=title_policy,
                upload_drafts=_parse_bool(os.getenv("CONFLUENCE_UPLOAD_DRAFTS"), False),
                restricted_article_policy=restricted_policy,
            )

        return cls(zendesk=zendesk, export=export, confluence=confluence)
