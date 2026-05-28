from capsulelab.core.document_store import DocumentStore


def test_read_returns_default_when_missing(tmp_path):
    store = DocumentStore(tmp_path / "missing.json", default={"key": "val"})
    assert store.read() == {"key": "val"}


def test_write_then_read(tmp_path):
    store = DocumentStore(tmp_path / "data.json")
    store.write({"a": 1, "b": [2, 3]})
    assert store.read() == {"a": 1, "b": [2, 3]}


def test_delete_returns_true_when_exists(tmp_path):
    store = DocumentStore(tmp_path / "data.json")
    store.write({"x": 1})
    assert store.delete() is True
    assert not store.path.exists()


def test_delete_returns_false_when_missing(tmp_path):
    store = DocumentStore(tmp_path / "nonexistent.json")
    assert store.delete() is False


def test_update_with_dict_merges(tmp_path):
    store = DocumentStore(tmp_path / "data.json")
    store.write({"a": 1})
    store.update({"b": 2})
    assert store.read() == {"a": 1, "b": 2}


def test_update_with_callable(tmp_path):
    store = DocumentStore(tmp_path / "counter.json")
    store.write({"count": 1})
    store.update(lambda data: {**data, "count": data["count"] + 1})
    assert store.read() == {"count": 2}


def test_write_creates_parent_dir(tmp_path):
    nested = tmp_path / "a" / "b" / "c" / "doc.json"
    store = DocumentStore(nested)
    store.write({"ok": True})
    assert nested.exists()


def test_custom_default(tmp_path):
    store = DocumentStore(tmp_path / "data.json", default=[])
    assert store.read() == []


def test_exists_checks_file(tmp_path):
    store = DocumentStore(tmp_path / "data.json")
    assert store.exists() is False
    store.write({})
    assert store.exists() is True
