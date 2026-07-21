import pytest

from auth import auth


@pytest.fixture(autouse=True)
def seeded_jwks(monkeypatch):
    monkeypatch.setattr(
        auth,
        "_JWKS",
        {
            "keys": [
                {
                    "kty": "RSA",
                    "kid": "test-kid",
                    "use": "sig",
                    "alg": "RS256",
                    "n": "some-modulus",
                    "e": "AQAB",
                }
            ]
        },
    )


def test_get_key_returns_matching_key():
    key = auth.get_key("test-kid")
    assert key == {
        "kty": "RSA",
        "kid": "test-kid",
        "use": "sig",
        "alg": "RS256",
        "n": "some-modulus",
        "e": "AQAB",
    }


def test_get_key_raises_for_unknown_kid():
    with pytest.raises(Exception, match="Public key not found"):
        auth.get_key("no-such-kid")
