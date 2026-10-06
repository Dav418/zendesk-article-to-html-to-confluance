from __future__ import annotations

import csv
import hashlib
import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from zendesk_confluence_migrator.config import AppConfig, ConfluenceSettings
from zendesk_confluence_migrator.confluence_client import ConfluenceClient
from zendesk_confluence_migrator.confluence_renderer import ConfluenceStorageRenderer
from zendesk_confluence_migrator.models import (
    ArticleRecord,
    ConfluencePageState,
    MigrationManifest,
    SectionRecord,
    UploadState,
)
from zendesk_confluence_migrator.naming import bounded_title, unique_title
from zendesk_confluence_migrator.selection import apply_article_limit, sections_for_articles


def article_content_fingerprint(article: ArticleRecord) -> str:
    payload = {
        "title": article.title,
        "body_html": article.body_html,
        "draft": article.draft,
        "assets": [
            {
                "file_name": asset.file_name,
                "relative_path": asset.relative_path,
                "inline": asset.inline,
                "image": asset.image,
            }
            for asset in article.assets
        ],
    }
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


@dataclass
class MigrationPlan:
    valid: bool
    root_title: str | None
    section_titles: dict[int, str]
    article_titles: dict[int, str]
    upload_article_ids: set[int]
    title_conflicts: list[dict[str, str]] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    article_limit: int | None = None
    articles_available: int = 0
    drafts_skipped: int = 0


class ConfluenceUploader:
    def __init__(
        self,
        *,
        config: AppConfig,
        client: ConfluenceClient,
        manifest: MigrationManifest,
        workspace_dir: Path,
    ) -> None:
        if config.confluence is None:
            raise ValueError("Confluence configuration is required")
        self._config = config
        self._settings: ConfluenceSettings = config.confluence
        self._client = client
        self._manifest = manifest
        self._workspace_dir = workspace_dir
        self._state_path = workspace_dir / "confluence-upload-state.json"
        self._preflight_path = workspace_dir / "confluence-preflight.json"
        self._renderer = ConfluenceStorageRenderer(manifest)

    def preflight(self, *, article_limit: int | None = None) -> MigrationPlan:
        if not self._manifest.export_ok:
            raise RuntimeError(
                "The Zendesk export did not finish cleanly, so nothing will be sent to "
                "Confluence. Look at migration-report.json in the export folder, then run "
                "`python main.py export` again."
            )
        logging.info("Checking Confluence target space and parent page...")
        space = self._client.get_space(self._settings.space_key)
        returned_key = str(space.get("key") or "")
        if returned_key and returned_key != self._settings.space_key:
            raise RuntimeError(
                f"Confluence returned space {returned_key!r}, expected {self._settings.space_key!r}"
            )

        parent = self._client.get_page(self._settings.parent_page_id)
        parent_space = parent.get("space")
        parent_space_key = str(parent_space.get("key") or "") if isinstance(parent_space, dict) else ""
        if parent_space_key and parent_space_key != self._settings.space_key:
            raise RuntimeError(
                "CONFLUENCE_PARENT_PAGE_ID belongs to a different space: "
                f"{parent_space_key!r}"
            )

        state = self._load_state_if_present()
        if state:
            self._validate_state_target(state)

        pages = self._client.list_pages_in_space(self._settings.space_key)
        pages_by_id = {str(page.get("id")): page for page in pages if page.get("id") is not None}
        own_ids = self._state_page_ids(state)
        external_titles: set[str] = {
            str(page.get("title") or "").casefold()
            for page in pages
            if page.get("id") is not None and str(page.get("id")) not in own_ids
        }

        if state:
            self._validate_state_pages(state, pages_by_id)

        eligible_ids = {
            article.id
            for article in self._manifest.articles
            if self._settings.upload_drafts or not article.draft
        }
        ordered_eligible = self._upload_articles(eligible_ids)
        selected_articles = apply_article_limit(ordered_eligible, article_limit)
        upload_article_ids = {article.id for article in selected_articles}
        selected_sections = sections_for_articles(
            self._manifest.sections,
            [article.section_id for article in selected_articles],
        )
        selected_section_ids = {section.id for section in selected_sections}
        skipped_drafts = [
            article for article in self._manifest.articles if article.id not in eligible_ids
        ]
        restricted = [article for article in selected_articles if article.restricted]

        warnings: list[str] = []
        if (
            self._manifest.article_limit is not None
            and self._manifest.articles_in_source is not None
            and len(self._manifest.articles) < self._manifest.articles_in_source
        ):
            warnings.append(
                "This export was created with an article limit and only contains "
                f"{len(self._manifest.articles)} of {self._manifest.articles_in_source} "
                "article(s). Re-run `python main.py export` without --limit before migrating "
                "the rest of the category."
            )
        if article_limit is not None and len(selected_articles) < len(ordered_eligible):
            warnings.append(
                f"Article limit is {article_limit}. This run includes the first "
                f"{len(selected_articles)} of {len(ordered_eligible)} article(s), in section "
                "and article order. Raise the limit, or omit it, to continue with the rest. "
                "Pages already created by this migration are reused. Section and category "
                "index pages in this batch list only this batch."
            )
        if state and article_limit is not None:
            outside_batch = [
                article_id for article_id in state.articles if article_id not in upload_article_ids
            ]
            if outside_batch:
                warnings.append(
                    f"Upload state already contains {len(outside_batch)} article page(s) outside "
                    "this batch. Those pages stay in Confluence and are not updated."
                )
        if skipped_drafts:
            warnings.append(
                f"{len(skipped_drafts)} draft article(s) will NOT be uploaded because "
                "CONFLUENCE_UPLOAD_DRAFTS=false."
            )
        if restricted:
            message = (
                f"{len(restricted)} Zendesk article(s) are marked restricted. Zendesk user-segment "
                "restrictions are not automatically recreated in Confluence; the new pages inherit "
                "the target Confluence hierarchy's permissions."
            )
            warnings.append(message)

        title_conflicts: list[dict[str, str]] = []
        used_planned: set[str] = set()
        self._reserve_titles_outside_batch(
            state,
            section_ids=selected_section_ids,
            article_ids=upload_article_ids,
            used_planned=used_planned,
        )

        root_title: str | None = None
        if self._settings.create_category_root:
            if state and state.root:
                root_title = state.root.title
                used_planned.add(root_title.casefold())
            elif state and state.planned_root_title:
                root_title = state.planned_root_title
                used_planned.add(root_title.casefold())
            else:
                base = self._settings.root_page_title or self._manifest.category_name
                root_title = self._plan_title(
                    base=base,
                    suffix_hint=f"category-{self._manifest.category_id}",
                    external_titles=external_titles,
                    used_planned=used_planned,
                    title_conflicts=title_conflicts,
                    entity="category root",
                )

        section_titles: dict[int, str] = {}
        for section in self._ordered_sections():
            if section.id not in selected_section_ids:
                continue
            if state and section.id in state.sections:
                title = state.sections[section.id].title
                if title.casefold() in used_planned:
                    raise RuntimeError(f"Upload state contains duplicate planned title: {title}")
                used_planned.add(title.casefold())
            elif state and section.id in state.planned_section_titles:
                title = state.planned_section_titles[section.id]
                if title.casefold() in used_planned:
                    raise RuntimeError(f"Upload state contains duplicate planned title: {title}")
                used_planned.add(title.casefold())
            else:
                title = self._plan_title(
                    base=section.name,
                    suffix_hint=f"section-{section.id}",
                    external_titles=external_titles,
                    used_planned=used_planned,
                    title_conflicts=title_conflicts,
                    entity=f"section {section.id}",
                )
            section_titles[section.id] = title

        article_titles: dict[int, str] = {}
        for article in selected_articles:
            if state and article.id in state.articles:
                title = state.articles[article.id].title
                if title.casefold() in used_planned:
                    raise RuntimeError(f"Upload state contains duplicate planned title: {title}")
                used_planned.add(title.casefold())
            elif state and article.id in state.planned_article_titles:
                title = state.planned_article_titles[article.id]
                if title.casefold() in used_planned:
                    raise RuntimeError(f"Upload state contains duplicate planned title: {title}")
                used_planned.add(title.casefold())
            else:
                title = self._plan_title(
                    base=article.title,
                    suffix_hint=f"article-{article.id}",
                    external_titles=external_titles,
                    used_planned=used_planned,
                    title_conflicts=title_conflicts,
                    entity=f"article {article.id}",
                )
            article_titles[article.id] = title

        valid = not title_conflicts
        if restricted and self._settings.restricted_article_policy == "fail":
            valid = False
            warnings.append(
                "CONFLUENCE_RESTRICTED_ARTICLE_POLICY=fail, so upload is blocked until the "
                "permission difference is explicitly addressed."
            )

        plan = MigrationPlan(
            valid=valid,
            root_title=root_title,
            section_titles=section_titles,
            article_titles=article_titles,
            upload_article_ids=upload_article_ids,
            title_conflicts=title_conflicts,
            warnings=warnings,
            article_limit=article_limit,
            articles_available=len(ordered_eligible),
            drafts_skipped=len(skipped_drafts),
        )
        self._write_preflight_report(plan, parent)
        self._print_preflight(plan)
        return plan

    def upload(self, *, article_limit: int | None = None) -> None:
        plan = self.preflight(article_limit=article_limit)
        if not plan.valid:
            raise RuntimeError(
                "Confluence preflight failed. No new pages were created. Review "
                f"{self._preflight_path}."
            )

        state = self._load_state_if_present()
        if state is None:
            state = UploadState(
                schema_version=1,
                category_id=self._manifest.category_id,
                confluence_base_url=self._settings.base_url,
                confluence_space_key=self._settings.space_key,
                configured_parent_page_id=self._settings.parent_page_id,
                create_category_root=self._settings.create_category_root,
                planned_root_title=plan.root_title,
                planned_section_titles=dict(plan.section_titles),
                planned_article_titles=dict(plan.article_titles),
            )
            state.save(self._state_path)
        else:
            self._validate_state_target(state)
            state.planned_root_title = plan.root_title
            state.planned_section_titles.update(plan.section_titles)
            state.planned_article_titles.update(plan.article_titles)
            state.save(self._state_path)

        root_parent_id = self._settings.parent_page_id
        category_url: str
        if self._settings.create_category_root:
            if state.root is None:
                logging.info("Creating category root page: %s", plan.root_title)
                page = self._client.create_page(
                    space_key=self._settings.space_key,
                    title=plan.root_title or self._manifest.category_name,
                    parent_page_id=self._settings.parent_page_id,
                    body_storage=self._placeholder("Zendesk category", self._manifest.category_id),
                )
                state.root = self._page_state(page, plan.root_title or self._manifest.category_name)
                state.save(self._state_path)
            root_parent_id = state.root.page_id
            category_url = state.root.url
        else:
            parent = self._client.get_page(self._settings.parent_page_id)
            category_url = self._client.page_url(parent, space_key=self._settings.space_key)

        planned_sections = [
            section for section in self._ordered_sections() if section.id in plan.section_titles
        ]
        for section in planned_sections:
            if section.id in state.sections:
                continue
            parent_page_id = root_parent_id
            if section.parent_section_id is not None and section.parent_section_id in state.sections:
                parent_page_id = state.sections[section.parent_section_id].page_id
            logging.info("Creating section page: %s", plan.section_titles[section.id])
            page = self._client.create_page(
                space_key=self._settings.space_key,
                title=plan.section_titles[section.id],
                parent_page_id=parent_page_id,
                body_storage=self._placeholder("Zendesk section", section.id),
            )
            state.sections[section.id] = self._page_state(page, plan.section_titles[section.id])
            state.save(self._state_path)

        upload_articles = self._upload_articles(plan.upload_article_ids)
        for article in upload_articles:
            if article.id in state.articles:
                continue
            parent_page_id = root_parent_id
            if article.section_id is not None and article.section_id in state.sections:
                parent_page_id = state.sections[article.section_id].page_id
            logging.info("Creating article page: %s", plan.article_titles[article.id])
            page = self._client.create_page(
                space_key=self._settings.space_key,
                title=plan.article_titles[article.id],
                parent_page_id=parent_page_id,
                body_storage=self._placeholder("Zendesk article", article.id),
            )
            state.articles[article.id] = self._page_state(page, plan.article_titles[article.id])
            state.save(self._state_path)

        article_urls = {article_id: page.url for article_id, page in state.articles.items()}
        section_urls = {section_id: page.url for section_id, page in state.sections.items()}

        report_rows: list[dict[str, object]] = []
        issues: list[dict[str, object]] = []
        for index, article in enumerate(upload_articles, start=1):
            page_state = state.articles[article.id]
            fingerprint = article_content_fingerprint(article)
            if state.completed_article_fingerprints.get(article.id) == fingerprint:
                logging.info(
                    "[%d/%d] Already uploaded, leaving %s unchanged",
                    index,
                    len(upload_articles),
                    page_state.title,
                )
                report_rows.append(
                    self._report_row(
                        article,
                        page_state,
                        content_status="already up to date",
                        assets_uploaded=0,
                        internal_links_rewritten=0,
                        attachment_links_rewritten=0,
                        images_rewritten=0,
                        unresolved_zendesk_links=0,
                    )
                )
                continue
            logging.info(
                "[%d/%d] Uploading assets/content for %s",
                index,
                len(upload_articles),
                page_state.title,
            )
            for asset in article.assets:
                path = self._workspace_dir / asset.relative_path
                if not path.is_file():
                    raise RuntimeError(
                        f"Exported asset is missing: {path}. Re-run the Zendesk export first."
                    )
                self._client.upload_attachment(page_id=page_state.page_id, file_path=path)

            body, stats, article_issues = self._renderer.render_article(
                article=article,
                article_urls=article_urls,
                section_urls=section_urls,
                category_url=category_url,
            )
            issues.extend(article_issues)
            self._client.update_page(
                page_id=page_state.page_id,
                space_key=self._settings.space_key,
                title=page_state.title,
                body_storage=body,
            )
            state.completed_article_fingerprints[article.id] = fingerprint
            state.save(self._state_path)
            report_rows.append(
                self._report_row(
                    article,
                    page_state,
                    content_status="uploaded",
                    assets_uploaded=len(article.assets),
                    internal_links_rewritten=stats.internal_links_rewritten,
                    attachment_links_rewritten=stats.attachment_links_rewritten,
                    images_rewritten=stats.images_rewritten,
                    unresolved_zendesk_links=stats.unresolved_zendesk_links,
                )
            )

        children_by_parent: dict[int | None, list[SectionRecord]] = {}
        for section in planned_sections:
            children_by_parent.setdefault(section.parent_section_id, []).append(section)
        articles_by_section: dict[int | None, list[ArticleRecord]] = {}
        for article in upload_articles:
            articles_by_section.setdefault(article.section_id, []).append(article)

        for section in reversed(planned_sections):
            body = self._renderer.render_section(
                section=section,
                child_sections=children_by_parent.get(section.id, []),
                articles=articles_by_section.get(section.id, []),
                section_urls=section_urls,
                article_urls=article_urls,
                category_url=category_url,
            )
            page_state = state.sections[section.id]
            self._client.update_page(
                page_id=page_state.page_id,
                space_key=self._settings.space_key,
                title=page_state.title,
                body_storage=body,
            )

        if self._settings.create_category_root and state.root is not None:
            section_ids = {section.id for section in planned_sections}
            top_level = [
                section
                for section in planned_sections
                if section.parent_section_id is None or section.parent_section_id not in section_ids
            ]
            body = self._renderer.render_category(
                top_level_sections=top_level,
                section_urls=section_urls,
                article_urls=article_urls,
                category_url=category_url,
            )
            self._client.update_page(
                page_id=state.root.page_id,
                space_key=self._settings.space_key,
                title=state.root.title,
                body_storage=body,
            )

        self._write_upload_report(report_rows, issues, state)
        print()
        print("=== Confluence upload complete ===")
        print(
            "Articles updated:       "
            f"{sum(1 for row in report_rows if row['content_status'] == 'uploaded')}"
        )
        print(
            "Articles already done:  "
            f"{sum(1 for row in report_rows if row['content_status'] == 'already up to date')}"
        )
        if plan.article_limit is not None:
            print(
                f"Article limit:          {plan.article_limit} of {plan.articles_available}"
            )
        print(f"Sections in state:      {len(state.sections)}")
        print(f"Unresolved links:       {sum(int(row['unresolved_zendesk_links']) for row in report_rows)}")
        print(f"State file:             {self._state_path}")
        print(f"Upload report:          {self._workspace_dir / 'confluence-upload-report.csv'}")
        if self._settings.create_category_root and state.root:
            print(f"Migration root:         {state.root.url}")

    def _plan_title(
        self,
        *,
        base: str,
        suffix_hint: str,
        external_titles: set[str],
        used_planned: set[str],
        title_conflicts: list[dict[str, str]],
        entity: str,
    ) -> str:
        base = bounded_title(base, fallback=f"Zendesk {suffix_hint}")
        folded = base.casefold()
        if folded not in external_titles and folded not in used_planned:
            used_planned.add(folded)
            return base

        if folded in used_planned:
            return unique_title(base, suffix_hint=suffix_hint, used_casefolded=used_planned)

        if self._settings.existing_title_policy == "suffix":
            combined = set(external_titles) | set(used_planned)
            title = unique_title(base, suffix_hint=suffix_hint, used_casefolded=combined)
            used_planned.add(title.casefold())
            return title

        title_conflicts.append({"entity": entity, "title": base})
        used_planned.add(folded)
        return base

    def _reserve_titles_outside_batch(
        self,
        state: UploadState | None,
        *,
        section_ids: set[int],
        article_ids: set[int],
        used_planned: set[str],
    ) -> None:
        """Hold titles of pages from earlier batches so this batch cannot reuse them."""
        if state is None:
            return
        for section_id, page in state.sections.items():
            if section_id not in section_ids:
                used_planned.add(page.title.casefold())
        for section_id, title in state.planned_section_titles.items():
            if section_id not in section_ids and section_id not in state.sections:
                used_planned.add(title.casefold())
        for article_id, page in state.articles.items():
            if article_id not in article_ids:
                used_planned.add(page.title.casefold())
        for article_id, title in state.planned_article_titles.items():
            if article_id not in article_ids and article_id not in state.articles:
                used_planned.add(title.casefold())

    def _ordered_sections(self) -> list[SectionRecord]:
        by_id = {section.id: section for section in self._manifest.sections}
        visited: set[int] = set()
        visiting: set[int] = set()
        ordered: list[SectionRecord] = []

        def visit(section: SectionRecord) -> None:
            if section.id in visited:
                return
            if section.id in visiting:
                raise RuntimeError("Zendesk section hierarchy contains a cycle")
            visiting.add(section.id)
            parent_id = section.parent_section_id
            if parent_id is not None and parent_id in by_id:
                visit(by_id[parent_id])
            visiting.remove(section.id)
            visited.add(section.id)
            ordered.append(section)

        for section in sorted(self._manifest.sections, key=self._section_sort_key):
            visit(section)
        return ordered

    def _upload_articles(self, article_ids: set[int]) -> list[ArticleRecord]:
        section_positions = {section.id: section.position for section in self._manifest.sections}
        return sorted(
            [article for article in self._manifest.articles if article.id in article_ids],
            key=lambda article: (
                section_positions.get(article.section_id)
                if section_positions.get(article.section_id) is not None
                else 1_000_000,
                article.position if article.position is not None else 1_000_000,
                article.title.casefold(),
            ),
        )

    def _section_sort_key(self, section: SectionRecord) -> tuple[int, str]:
        return (
            section.position if section.position is not None else 1_000_000,
            section.name.casefold(),
        )

    def _page_state(self, page: dict[str, Any], title: str) -> ConfluencePageState:
        page_id = str(page.get("id") or "")
        if not page_id:
            raise RuntimeError("Confluence create-page response did not include a page ID")
        return ConfluencePageState(
            page_id=page_id,
            title=title,
            url=self._client.page_url(page, space_key=self._settings.space_key),
        )

    def _load_state_if_present(self) -> UploadState | None:
        return UploadState.load(self._state_path) if self._state_path.exists() else None

    def _validate_state_target(self, state: UploadState) -> None:
        expected = (
            self._manifest.category_id,
            self._settings.base_url,
            self._settings.space_key,
            self._settings.parent_page_id,
            self._settings.create_category_root,
        )
        actual = (
            state.category_id,
            state.confluence_base_url,
            state.confluence_space_key,
            state.configured_parent_page_id,
            state.create_category_root,
        )
        if actual != expected:
            raise RuntimeError(
                "confluence-upload-state.json belongs to a different source/target configuration. "
                "Do not delete it if pages were already created; review the state before proceeding."
            )

    def _state_page_ids(self, state: UploadState | None) -> set[str]:
        if state is None:
            return set()
        ids = {page.page_id for page in state.sections.values()} | {
            page.page_id for page in state.articles.values()
        }
        if state.root:
            ids.add(state.root.page_id)
        return ids

    def _validate_state_pages(self, state: UploadState, pages_by_id: dict[str, dict[str, Any]]) -> None:
        states: list[ConfluencePageState] = list(state.sections.values()) + list(state.articles.values())
        if state.root:
            states.append(state.root)
        for page_state in states:
            current = pages_by_id.get(page_state.page_id)
            if current is None:
                raise RuntimeError(
                    f"A page recorded in upload state no longer exists or is not visible: "
                    f"{page_state.page_id} ({page_state.title})."
                )
            current_title = str(current.get("title") or "")
            if current_title != page_state.title:
                raise RuntimeError(
                    f"Confluence page {page_state.page_id} was renamed from "
                    f"{page_state.title!r} to {current_title!r} after migration state was saved. "
                    "Refusing to overwrite it automatically."
                )

    def _write_preflight_report(self, plan: MigrationPlan, parent: dict[str, Any]) -> None:
        payload = {
            "valid": plan.valid,
            "target": {
                "base_url": self._settings.base_url,
                "space_key": self._settings.space_key,
                "parent_page_id": self._settings.parent_page_id,
                "parent_page_title": parent.get("title"),
                "create_category_root": self._settings.create_category_root,
                "root_title": plan.root_title,
            },
            "counts": {
                "sections": len(plan.section_titles),
                "articles_available": plan.articles_available,
                "article_limit": plan.article_limit,
                "articles_to_upload": len(plan.article_titles),
                "drafts_skipped": plan.drafts_skipped,
                "restricted_articles": sum(
                    1
                    for article in self._manifest.articles
                    if article.id in plan.upload_article_ids and article.restricted
                ),
            },
            "title_conflicts": plan.title_conflicts,
            "warnings": plan.warnings,
            "planned_section_titles": {
                str(key): value for key, value in plan.section_titles.items()
            },
            "planned_article_titles": {
                str(key): value for key, value in plan.article_titles.items()
            },
        }
        self._preflight_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    def _print_preflight(self, plan: MigrationPlan) -> None:
        print()
        print("=== Confluence preflight ===")
        print(f"Space:                   {self._settings.space_key}")
        print(f"Parent page ID:          {self._settings.parent_page_id}")
        print(f"Create category root:    {self._settings.create_category_root}")
        if plan.article_limit is None:
            print(f"Article limit:           none ({plan.articles_available} available)")
        else:
            print(
                f"Article limit:           {plan.article_limit} of {plan.articles_available}"
            )
        print(f"Sections planned:        {len(plan.section_titles)}")
        print(f"Articles planned:        {len(plan.article_titles)}")
        print(f"Title conflicts:         {len(plan.title_conflicts)}")
        for warning in plan.warnings:
            print(f"WARNING: {warning}")
        if plan.title_conflicts:
            print("Conflicting titles:")
            for conflict in plan.title_conflicts[:20]:
                print(f"  - {conflict['entity']}: {conflict['title']}")
            if len(plan.title_conflicts) > 20:
                print(f"  ... and {len(plan.title_conflicts) - 20} more")
        print(f"Preflight report:        {self._preflight_path}")
        print(f"Result:                  {'PASS' if plan.valid else 'FAIL'}")

    def _report_row(
        self,
        article: ArticleRecord,
        page_state: ConfluencePageState,
        *,
        content_status: str,
        assets_uploaded: int,
        internal_links_rewritten: int,
        attachment_links_rewritten: int,
        images_rewritten: int,
        unresolved_zendesk_links: int,
    ) -> dict[str, object]:
        return {
            "zendesk_article_id": article.id,
            "zendesk_title": article.title,
            "confluence_title": page_state.title,
            "confluence_page_id": page_state.page_id,
            "confluence_url": page_state.url,
            "section_id": article.section_id,
            "draft": article.draft,
            "restricted_in_zendesk": article.restricted,
            "content_status": content_status,
            "assets_uploaded": assets_uploaded,
            "internal_links_rewritten": internal_links_rewritten,
            "attachment_links_rewritten": attachment_links_rewritten,
            "images_rewritten": images_rewritten,
            "unresolved_zendesk_links": unresolved_zendesk_links,
        }

    def _write_upload_report(
        self,
        rows: list[dict[str, object]],
        issues: list[dict[str, object]],
        state: UploadState,
    ) -> None:
        csv_path = self._workspace_dir / "confluence-upload-report.csv"
        columns = [
            "zendesk_article_id",
            "zendesk_title",
            "confluence_title",
            "confluence_page_id",
            "confluence_url",
            "section_id",
            "draft",
            "restricted_in_zendesk",
            "content_status",
            "assets_uploaded",
            "internal_links_rewritten",
            "attachment_links_rewritten",
            "images_rewritten",
            "unresolved_zendesk_links",
        ]
        with csv_path.open("w", newline="", encoding="utf-8-sig") as handle:
            writer = csv.DictWriter(handle, fieldnames=columns)
            writer.writeheader()
            writer.writerows(rows)

        json_path = self._workspace_dir / "confluence-upload-report.json"
        payload = {
            "target": {
                "base_url": self._settings.base_url,
                "space_key": self._settings.space_key,
                "parent_page_id": self._settings.parent_page_id,
                "root_page": (
                    {
                        "id": state.root.page_id,
                        "title": state.root.title,
                        "url": state.root.url,
                    }
                    if state.root
                    else None
                ),
            },
            "articles": rows,
            "issues": issues,
        }
        json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    def _placeholder(self, kind: str, source_id: int) -> str:
        return (
            "<p><em>Zendesk migration in progress. This placeholder will be replaced "
            f"automatically.</em></p><!-- {kind} {source_id} -->"
        )
