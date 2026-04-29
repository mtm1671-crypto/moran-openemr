from app.main import _local_cors_origin_regex


def test_local_cors_origin_regex_allows_localhost_dev_ports_only_in_local_env() -> None:
    assert _local_cors_origin_regex("local") == r"https?://(localhost|127\.0\.0\.1):\d+"
    assert _local_cors_origin_regex("production") is None
