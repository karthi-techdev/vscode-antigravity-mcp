import pytest
from server.auth import verify_token


def test_dynamic_token_adoption():
    # Pre-configured tokens work
    # Any custom token with >= 6 chars gets an isolated user_id
    user_a = verify_token("mcp-testing-123")
    assert user_a is not None
    assert user_a.startswith("user_")

    user_b = verify_token("another-custom-secret-key-456")
    assert user_b is not None
    assert user_b.startswith("user_")

    # Tokens must be completely isolated
    assert user_a != user_b

    # The same token always derives the same user
    assert verify_token("mcp-testing-123") == user_a

    # Short tokens (<6 chars) are rejected for security
    assert verify_token("123") is None
