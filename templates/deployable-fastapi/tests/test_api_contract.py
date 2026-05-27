from app.main import health, root


def test_health_contract():
    assert health() == {"status": "healthy"}


def test_root_contract():
    payload = root()
    assert payload["docs"] == "/docs"
