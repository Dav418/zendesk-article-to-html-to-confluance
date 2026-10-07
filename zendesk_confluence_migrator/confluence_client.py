from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any
from urllib.parse import urljoin

import requests
from requests.adapters import HTTPAdapter
from requests.auth import HTTPBasicAuth
from urllib3.util.retry import Retry

from zendesk_confluence_migrator.config import ConfluenceSettings, ExportSettings


_MAX_RATE_LIMIT_ATTEMPTS = 6
_MAX_WAIT_SECONDS = 15 * 60


def rate_limit_wait_seconds(retry_after: str | None, attempt: int) -> int:
    """Seconds to wait after Confluence says to slow down."""
    parsed = _parse_retry_after(retry_after)
    if parsed is None:
        return min(32, 2 ** max(attempt, 0))
    return parsed


def _parse_retry_after(value: str | None) -> int | None:
    if value is None:
        return None
    text = value.strip()
    if not text:
        return None
    try:
        return max(0, int(float(text)))
    except ValueError:
        pass
    try:
        moment = parsedate_to_datetime(text)
    except (TypeError, ValueError, IndexError, OverflowError):
        return None
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    return max(0, int((moment - datetime.now(timezone.utc)).total_seconds()))


class ConfluenceClient:
    def __init__(self, settings: ConfluenceSettings, export_settings: ExportSettings) -> None:
        self._settings = settings
        self._export_settings = export_settings
        self._wiki_base = f"{settings.base_url}/wiki"
        self._api_base = self._wiki_base
        self._login_description = "CONFLUENCE_EMAIL and CONFLUENCE_API_TOKEN"
        self._uses_client_credentials = bool(settings.oauth_client_id and settings.oauth_client_secret)
        self._token_deadline = 0.0
        self._session = requests.Session()
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
        self._session.mount("https://", adapter)
        self._session.headers.update(
            {
                "Accept": "application/json",
                "User-Agent": "zendesk-confluence-migrator/2.0",
            }
        )
        if self._uses_client_credentials:
            self._login_description = "CONFLUENCE_OAUTH_CLIENT_ID and CONFLUENCE_OAUTH_CLIENT_SECRET"
            self._api_base = self._service_account_api_base()
        else:
            assert settings.email is not None
            assert settings.api_token is not None
            self._session.auth = HTTPBasicAuth(settings.email, settings.api_token)

    def get_space(self, space_key: str) -> dict[str, Any]:
        return self._request_json("GET", f"/rest/api/space/{space_key}")

    def get_page(self, page_id: str) -> dict[str, Any]:
        return self._request_json(
            "GET",
            f"/rest/api/content/{page_id}",
            params={"expand": "space,version,ancestors"},
        )

    def list_pages_in_space(self, space_key: str) -> list[dict[str, Any]]:
        # An archived or draft page still reserves its title. Confluence rejects a new
        # page with that title, so those pages have to be included in the conflict check.
        pages: list[dict[str, Any]] = []
        seen: set[str] = set()
        for status in ("current", "archived", "draft"):
            try:
                found = self._list_pages(space_key, status=status)
            except RuntimeError as exc:
                if status != "current" and "403" in str(exc):
                    logging.warning(
                        "Confluence did not allow listing %s pages. Continuing without them.",
                        status,
                    )
                    continue
                raise
            for page in found:
                page_id = str(page.get("id") or "")
                if page_id and page_id in seen:
                    continue
                if page_id:
                    seen.add(page_id)
                pages.append(page)
        return pages

    def _list_pages(self, space_key: str, *, status: str) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        start = 0
        limit = 100
        while True:
            payload = self._request_json(
                "GET",
                "/rest/api/content",
                params={
                    "spaceKey": space_key,
                    "type": "page",
                    "status": status,
                    "limit": limit,
                    "start": start,
                },
            )
            page_results = payload.get("results", [])
            if not isinstance(page_results, list):
                raise RuntimeError("Confluence content response did not contain a results list")
            results.extend(item for item in page_results if isinstance(item, dict))
            size = int(payload.get("size", len(page_results)) or 0)
            links = payload.get("_links")
            if size == 0 or not (isinstance(links, dict) and links.get("next")):
                break
            start += size
        return results

    def create_page(
        self,
        *,
        space_key: str,
        title: str,
        parent_page_id: str,
        body_storage: str,
    ) -> dict[str, Any]:
        payload = {
            "type": "page",
            "title": title,
            "space": {"key": space_key},
            "ancestors": [{"id": str(parent_page_id)}],
            "body": {
                "storage": {
                    "value": body_storage,
                    "representation": "storage",
                }
            },
        }
        return self._request_json("POST", "/rest/api/content", json=payload)

    def update_page(
        self,
        *,
        page_id: str,
        space_key: str,
        title: str,
        body_storage: str,
    ) -> dict[str, Any]:
        current = self.get_page(page_id)
        version = current.get("version")
        if not isinstance(version, dict) or version.get("number") is None:
            raise RuntimeError(f"Confluence page {page_id} did not return a version number")
        payload = {
            "id": str(page_id),
            "type": "page",
            "title": title,
            "space": {"key": space_key},
            "body": {
                "storage": {
                    "value": body_storage,
                    "representation": "storage",
                }
            },
            "version": {
                "number": int(version["number"]) + 1,
                "minorEdit": True,
                "message": "Zendesk Help Center migration",
            },
        }
        return self._request_json("PUT", f"/rest/api/content/{page_id}", json=payload)

    def upload_attachment(self, *, page_id: str, file_path: Path) -> dict[str, Any]:
        url = f"{self._api_base}/rest/api/content/{page_id}/child/attachment"
        operation = f"upload attachment {file_path.name}"
        response: requests.Response | None = None
        refreshed = False
        for attempt in range(_MAX_RATE_LIMIT_ATTEMPTS):
            self._ensure_access_token()
            with file_path.open("rb") as handle:
                response = self._session.put(
                    url,
                    headers={"X-Atlassian-Token": "nocheck"},
                    files={"file": (file_path.name, handle)},
                    data={
                        "minorEdit": "true",
                        "comment": "Migrated from Zendesk Help Center",
                    },
                    timeout=self._export_settings.request_timeout_seconds,
                )
            if response.status_code == 401 and self._uses_client_credentials and not refreshed:
                self._token_deadline = 0.0
                refreshed = True
                continue
            if self._wait_for_rate_limit(response, attempt, operation):
                continue
            break
        assert response is not None
        self._pause_if_near_burst_limit(response)
        self._raise_for_response(response, operation=operation)
        payload = response.json()
        if not isinstance(payload, dict):
            raise RuntimeError("Confluence returned a non-object attachment response")
        return payload

    def page_url(self, page: dict[str, Any], *, space_key: str | None = None) -> str:
        links = page.get("_links")
        if isinstance(links, dict) and links.get("webui"):
            webui = str(links["webui"])
            if webui.startswith("/wiki/"):
                return f"{self._settings.base_url}{webui}"
            return urljoin(f"{self._wiki_base}/", webui.lstrip("/"))
        page_id = str(page.get("id") or "")
        key = space_key or self._settings.space_key
        return f"{self._wiki_base}/spaces/{key}/pages/{page_id}"

    def _request_json(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        operation = f"{method} {path}"
        response: requests.Response | None = None
        refreshed = False
        for attempt in range(_MAX_RATE_LIMIT_ATTEMPTS):
            self._ensure_access_token()
            response = self._session.request(
                method,
                f"{self._api_base}{path}",
                params=params,
                json=json,
                headers={"Content-Type": "application/json"} if json is not None else None,
                timeout=self._export_settings.request_timeout_seconds,
            )
            if response.status_code == 401 and self._uses_client_credentials and not refreshed:
                self._token_deadline = 0.0
                refreshed = True
                continue
            if self._wait_for_rate_limit(response, attempt, operation):
                continue
            break
        assert response is not None
        self._pause_if_near_burst_limit(response)
        self._raise_for_response(response, operation=operation)
        payload = response.json()
        if not isinstance(payload, dict):
            raise RuntimeError("Confluence returned a non-object JSON response")
        return payload

    def _service_account_api_base(self) -> str:
        response = requests.get(
            f"{self._settings.base_url}/_edge/tenant_info",
            timeout=self._export_settings.request_timeout_seconds,
        )
        try:
            payload = response.json()
        except ValueError:
            payload = None
        cloud_id = payload.get("cloudId") if isinstance(payload, dict) else None
        if response.status_code != 200 or not isinstance(cloud_id, str) or not cloud_id.strip():
            raise RuntimeError(
                "Confluence did not return a cloud ID for "
                f"{self._settings.base_url}. Check CONFLUENCE_BASE_URL."
            )
        return f"https://api.atlassian.com/ex/confluence/{cloud_id}/wiki"

    def _ensure_access_token(self) -> None:
        if not self._uses_client_credentials or time.monotonic() < self._token_deadline:
            return
        client_id = self._settings.oauth_client_id
        client_secret = self._settings.oauth_client_secret
        assert client_id is not None and client_secret is not None
        logging.info("Asking Confluence for an access token using the OAuth client ID and secret.")
        response = requests.post(
            "https://auth.atlassian.com/oauth/token",
            data={
                "grant_type": "client_credentials",
                "client_id": client_id,
                "client_secret": client_secret,
            },
            headers={"Accept": "application/json"},
            timeout=self._export_settings.request_timeout_seconds,
        )
        try:
            parsed = response.json()
        except ValueError:
            parsed = None
        payload = parsed if isinstance(parsed, dict) else {}
        if response.status_code != 200:
            detail = payload.get("error_description") or payload.get("error") or "no details"
            raise RuntimeError(
                "Confluence refused the OAuth client ID and secret "
                f"(HTTP {response.status_code}: {detail}). "
                "Check CONFLUENCE_OAUTH_CLIENT_ID and CONFLUENCE_OAUTH_CLIENT_SECRET."
            )
        token = payload.get("access_token")
        if not isinstance(token, str) or not token.strip():
            raise RuntimeError("Confluence did not return an access token for the OAuth client.")
        expires_in = payload.get("expires_in")
        lifetime = expires_in if isinstance(expires_in, int) and expires_in > 0 else 3600
        self._session.headers["Authorization"] = f"Bearer {token}"
        self._token_deadline = time.monotonic() + max(30, lifetime - 120)

    def _wait_for_rate_limit(
        self,
        response: requests.Response,
        attempt: int,
        operation: str,
    ) -> bool:
        limited = response.status_code == 429 or (
            response.status_code == 503 and bool(response.headers.get("Retry-After"))
        )
        if not limited or attempt >= _MAX_RATE_LIMIT_ATTEMPTS - 1:
            return False
        wait = rate_limit_wait_seconds(response.headers.get("Retry-After"), attempt)
        if wait > _MAX_WAIT_SECONDS:
            minutes = max(1, (wait + 59) // 60)
            raise RuntimeError(
                "Confluence is limiting requests and asked for a wait of about "
                f"{minutes} minutes. Run the same command again after that. "
                "Pages already created will be reused."
            )
        logging.warning(
            "Confluence is busy during %s and asked this tool to wait %s seconds. "
            "Waiting. Pages already created are saved.",
            operation,
            wait,
        )
        time.sleep(wait)
        return True

    def _pause_if_near_burst_limit(self, response: requests.Response) -> None:
        remaining = response.headers.get("X-RateLimit-Remaining")
        if remaining is None:
            return
        try:
            left = int(remaining)
        except ValueError:
            return
        if left <= 1:
            logging.info("Confluence is close to its short request limit. Pausing for 1 second.")
            time.sleep(1)

    def _raise_for_response(self, response: requests.Response, *, operation: str) -> None:
        if response.status_code == 429:
            raise RuntimeError(
                "Confluence is still limiting requests after several waits. "
                "Run the same command again in a few minutes. "
                "Pages already created will be reused."
            )
        if response.status_code == 401:
            raise RuntimeError(
                "Confluence returned 401 Unauthorized. "
                f"The login used was {self._login_description}."
            )
        if response.status_code == 403:
            raise RuntimeError(
                "Confluence returned 403 Forbidden. The authenticated user may not have the "
                "required permission in the target space/page."
            )
        if response.status_code == 404:
            raise RuntimeError(
                f"Confluence returned 404 for {operation}. Check the site URL, space key, "
                "and parent/page IDs."
            )
        if response.status_code >= 400:
            body = response.text[:2000]
            raise RuntimeError(
                f"Confluence {operation} failed with HTTP {response.status_code}: {body}"
            )
