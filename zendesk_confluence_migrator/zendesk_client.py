from __future__ import annotations

import logging
from collections.abc import Iterator
from typing import Any
from urllib.parse import urljoin, urlparse

import requests
from requests.adapters import HTTPAdapter
from requests.auth import HTTPBasicAuth
from urllib3.util.retry import Retry

from zendesk_confluence_migrator.config import ExportSettings, ZendeskSettings

logger = logging.getLogger(__name__)
# 48 hours is the longest access-token lifetime Zendesk allows.
_OAUTH_TOKEN_LIFETIME_SECONDS = 172800


class ZendeskClient:
    def __init__(self, settings: ZendeskSettings, export_settings: ExportSettings) -> None:
        self._settings = settings
        self._export_settings = export_settings
        self._login_description = "the Zendesk email and API token"
        self._authenticated_session = self._build_session(authenticated=True)
        self._public_session = self._build_session(authenticated=False)

    def _build_session(self, *, authenticated: bool) -> requests.Session:
        session = requests.Session()
        retry = Retry(
            total=5,
            connect=5,
            read=5,
            status=5,
            backoff_factor=1.0,
            status_forcelist=(429, 500, 502, 503, 504),
            allowed_methods=frozenset({"GET"}),
            respect_retry_after_header=True,
            raise_on_status=False,
        )
        adapter = HTTPAdapter(max_retries=retry)
        session.mount("https://", adapter)
        session.mount("http://", adapter)
        session.headers.update(
            {
                "Accept": "application/json",
                "User-Agent": "zendesk-confluence-migrator/2.0",
            }
        )

        if authenticated:
            access_token = self._oauth_access_token()
            if access_token:
                session.headers["Authorization"] = f"Bearer {access_token}"
            else:
                assert self._settings.email is not None
                assert self._settings.api_token is not None
                self._login_description = "ZENDESK_EMAIL and ZENDESK_API_TOKEN"
                session.auth = HTTPBasicAuth(
                    f"{self._settings.email}/token",
                    self._settings.api_token,
                )
        return session

    def _oauth_access_token(self) -> str | None:
        client_id = self._settings.oauth_client_id
        client_secret = self._settings.oauth_client_secret
        if client_id and client_secret:
            self._login_description = "ZENDESK_OAUTH_CLIENT_ID and ZENDESK_OAUTH_CLIENT_SECRET"
            logger.info("Asking Zendesk for an access token using the OAuth client Identifier and Secret.")
            return self._exchange_client_credentials(client_id, client_secret)
        return None

    def _exchange_client_credentials(self, client_id: str, client_secret: str) -> str:
        response = requests.post(
            f"{self._settings.origin}/oauth/tokens",
            json={
                "grant_type": "client_credentials",
                "client_id": client_id,
                "client_secret": client_secret,
                "scope": "hc:read",
                "expires_in": _OAUTH_TOKEN_LIFETIME_SECONDS,
            },
            headers={"Accept": "application/json"},
            timeout=self._export_settings.request_timeout_seconds,
        )
        payload: dict[str, Any] = {}
        try:
            parsed = response.json()
        except ValueError:
            parsed = None
        if isinstance(parsed, dict):
            payload = parsed
        if response.status_code != 200:
            detail = payload.get("error_description") or payload.get("error") or "no details"
            raise RuntimeError(
                "Zendesk refused the OAuth client Identifier and Secret "
                f"(HTTP {response.status_code}: {detail}). "
                "Check ZENDESK_OAUTH_CLIENT_ID and ZENDESK_OAUTH_CLIENT_SECRET. "
                "The OAuth client must be Confidential and must allow the hc:read scope."
            )
        token = payload.get("access_token")
        if not isinstance(token, str) or not token.strip():
            raise RuntimeError("Zendesk did not return an access token for the OAuth client.")
        return token

    def get_category(self) -> dict[str, Any]:
        url = (
            f"{self._settings.origin}/api/v2/help_center/{self._settings.locale}/"
            f"categories/{self._settings.category_id}.json"
        )
        payload = self._get_json(url)
        category = payload.get("category")
        if not isinstance(category, dict):
            raise RuntimeError("Zendesk category response did not contain a category")
        return category

    def list_sections(self) -> list[dict[str, Any]]:
        url = (
            f"{self._settings.origin}/api/v2/help_center/{self._settings.locale}/"
            f"categories/{self._settings.category_id}/sections.json"
        )
        return list(self._paginate(url, "sections"))

    def list_articles(self) -> list[dict[str, Any]]:
        url = (
            f"{self._settings.origin}/api/v2/help_center/{self._settings.locale}/"
            f"categories/{self._settings.category_id}/articles.json"
        )
        return list(self._paginate(url, "articles"))

    def list_article_attachments(self, article_id: int) -> list[dict[str, Any]]:
        url = (
            f"{self._settings.origin}/api/v2/help_center/{self._settings.locale}/"
            f"articles/{article_id}/attachments.json"
        )
        return list(self._paginate(url, "article_attachments"))

    def download(self, url: str) -> tuple[bytes, str | None, str]:
        absolute_url = urljoin(self._settings.origin, url)
        parsed = urlparse(absolute_url)
        session = (
            self._authenticated_session
            if parsed.hostname and parsed.hostname.lower() == self._settings.host
            else self._public_session
        )
        response = session.get(
            absolute_url,
            timeout=self._export_settings.request_timeout_seconds,
            stream=True,
        )
        response.raise_for_status()
        return response.content, response.headers.get("Content-Type"), response.url

    def _paginate(self, url: str, collection_key: str) -> Iterator[dict[str, Any]]:
        next_url: str | None = url
        params: dict[str, Any] | None = {"page[size]": 100}

        while next_url:
            payload = self._get_json(next_url, params=params)
            params = None
            items = payload.get(collection_key, [])
            if not isinstance(items, list):
                raise RuntimeError(f"Zendesk response field {collection_key!r} was not a list")
            for item in items:
                if isinstance(item, dict):
                    yield item

            meta = payload.get("meta")
            links = payload.get("links")
            if isinstance(meta, dict) and "has_more" in meta:
                if not meta.get("has_more"):
                    next_url = None
                elif isinstance(links, dict) and links.get("next"):
                    next_url = str(links["next"])
                else:
                    raise RuntimeError(
                        "Zendesk cursor pagination reported more data but did not provide links.next"
                    )
                continue

            raw_next_page = payload.get("next_page")
            next_url = str(raw_next_page) if raw_next_page else None

    def _get_json(
        self,
        url: str,
        *,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        self._assert_zendesk_url(url)
        response = self._authenticated_session.get(
            url,
            params=params,
            timeout=self._export_settings.request_timeout_seconds,
        )
        if response.status_code == 401:
            raise RuntimeError(
                "Zendesk returned 401 Unauthorized. "
                f"The login used was {self._login_description}."
            )
        if response.status_code == 403:
            raise RuntimeError(
                "Zendesk returned 403 Forbidden. The authenticated user may not be allowed "
                "to read this Help Center content."
            )
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, dict):
            raise RuntimeError("Zendesk returned a non-object JSON response")
        return payload

    def _assert_zendesk_url(self, url: str) -> None:
        parsed = urlparse(url)
        if not parsed.hostname or parsed.hostname.lower() != self._settings.host:
            logging.error("Refusing authenticated request to unexpected host: %s", url)
            raise RuntimeError("Zendesk pagination/API URL changed to an unexpected host")
