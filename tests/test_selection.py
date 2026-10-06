from zendesk_confluence_migrator.models import SectionRecord
from zendesk_confluence_migrator.selection import apply_article_limit, sections_for_articles


def _section(section_id: int, parent_id: int | None) -> SectionRecord:
    return SectionRecord(
        id=section_id,
        name=f"Section {section_id}",
        description_html="",
        source_url=None,
        parent_section_id=parent_id,
        position=section_id,
    )


def test_apply_article_limit_returns_the_first_n_items():
    assert apply_article_limit(["a", "b", "c"], 2) == ["a", "b"]


def test_apply_article_limit_without_a_limit_returns_everything():
    assert apply_article_limit(["a", "b"], None) == ["a", "b"]


def test_sections_for_articles_keeps_the_parent_chain_only():
    sections = [_section(1, None), _section(2, 1), _section(3, None)]
    selected = sections_for_articles(sections, [2, None])
    assert [section.id for section in selected] == [1, 2]
