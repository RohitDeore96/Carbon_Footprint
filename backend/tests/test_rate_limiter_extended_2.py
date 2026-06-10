"""Extended tests for rate_limiter.py — covers _is_valid_ip edge cases."""

from app.middleware.rate_limiter import _is_valid_ip


class TestIsValidIpEdgeCases:
    """Tests for _is_valid_ip with various edge cases."""

    def test_empty_string_is_invalid(self) -> None:
        """Verify empty string returns False."""
        assert _is_valid_ip("") is False

    def test_very_long_string_is_invalid(self) -> None:
        """Verify strings longer than 45 chars return False."""
        assert _is_valid_ip("a" * 46) is False

    def test_valid_ipv4(self) -> None:
        """Verify valid IPv4 address returns True."""
        assert _is_valid_ip("192.168.1.1") is True

    def test_valid_ipv6(self) -> None:
        """Verify valid IPv6 address returns True."""
        assert _is_valid_ip("::1") is True

    def test_hostname_is_invalid(self) -> None:
        """Verify hostname strings return False."""
        assert _is_valid_ip("example.com") is False

    def test_random_text_is_invalid(self) -> None:
        """Verify random non-IP text returns False."""
        assert _is_valid_ip("not-an-ip") is False
