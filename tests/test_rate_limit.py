from zendesk_confluence_migrator.confluence_client import rate_limit_wait_seconds


def test_rate_limit_wait_uses_retry_after_seconds():
    assert rate_limit_wait_seconds("12", attempt=0) == 12


def test_rate_limit_wait_backs_off_when_retry_after_is_missing():
    assert rate_limit_wait_seconds(None, attempt=0) == 1
    assert rate_limit_wait_seconds(None, attempt=3) == 8
    assert rate_limit_wait_seconds(None, attempt=10) == 32
