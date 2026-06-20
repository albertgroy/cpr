import hashlib

from cpr.cli.cache import ClientCache, cache_key, normalize_help_text, normalize_sub_path


def test_cache_key_protocol_algorithm():
    h = hashlib.sha256()
    h.update(b"1\nprompt\nsdk\ninstall/java\nen-US\n")
    h.update(b"line1\nline2")
    assert cache_key("sdk", [" Install ", "JAVA"], "line1\r\nline2\n\n", "en-US", "prompt") == h.hexdigest()
    assert normalize_sub_path([" A ", "", "b"]) == "a/b"
    assert normalize_help_text("x\r\n") == b"x"


def test_cache_hit_miss_schema_cleanup(tmp_path):
    path = tmp_path / "cache.sqlite"
    cache = ClientCache(path, schema_version="1")
    assert cache.get("missing") is None
    cache.put("k", "p1", {"schema_version": "1", "prompt_version": "p1"})
    assert cache.get_last_prompt_version() == "p1"
    assert cache.get("k")["prompt_version"] == "p1"
    cache.close()
    other = ClientCache(path, schema_version="2")
    assert other.get("k") is None
    other.close()
