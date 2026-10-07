from __future__ import annotations

from collections.abc import Iterable, Sequence
from typing import TypeVar

from zendesk_confluence_migrator.models import SectionRecord


T = TypeVar("T")


def upload_batches(total: int, *, first: int = 5, size: int = 50) -> list[int]:
    """Article counts to upload, each one including every article before it.

    A category of 120 becomes ``[5, 50, 100, 120]``. The first batch is the
    preview. Later batches add the next articles, reuse the earlier pages, and
    update links in those earlier pages.
    """
    if total <= 0:
        return []
    if first <= 0 or size <= 0:
        raise ValueError("Batch sizes must be positive")
    if total <= first:
        return [total]
    batches = [first]
    current = max(size, first)
    while current < total:
        if current != batches[-1]:
            batches.append(current)
        current += size
    if batches[-1] != total:
        batches.append(total)
    return batches


def apply_article_limit(items: Sequence[T], limit: int | None) -> list[T]:
    """Return the first ``limit`` items, or every item when ``limit`` is omitted."""
    if limit is None:
        return list(items)
    if limit <= 0:
        raise ValueError("Article limit must be a positive integer")
    return list(items[:limit])


def sections_for_articles(
    sections: Sequence[SectionRecord],
    section_ids: Iterable[int | None],
) -> list[SectionRecord]:
    """Keep the sections that contain the selected articles, plus their parent sections."""
    by_id = {section.id: section for section in sections}
    needed: set[int] = set()
    for section_id in section_ids:
        current = section_id
        chain: set[int] = set()
        while current is not None and current in by_id and current not in needed:
            if current in chain:
                break
            chain.add(current)
            needed.add(current)
            current = by_id[current].parent_section_id
    return [section for section in sections if section.id in needed]
