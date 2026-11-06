# /// script
# requires-python = ">=3.11"
# dependencies = ["nats-py>=2.9", "pytest"]
# ///
import json, sys, pathlib, pytest
sys.path.insert(0, str(pathlib.Path(__file__).parent))
import watch


def test_default_subjects_without_file():
    watch.load_subjects(None)
    assert watch.WATCHES["asks"][0] == ["mesa.pane.*.ask"]


def test_file_overrides_only_named(tmp_path, monkeypatch):
    saved = dict(watch.WATCHES)
    f = tmp_path / "s.json"
    f.write_text(json.dumps({"asks": ["x.ask.*"]}))
    try:
        watch.load_subjects(str(f))
        assert watch.WATCHES["asks"][0] == ["x.ask.*"]
        assert watch.WATCHES["llm"][0] == ["mesa.llm.>"]
    finally:
        watch.WATCHES.update(saved)


@pytest.mark.parametrize("body", ['{"nope": ["a"]}', '{"asks": []}', '[1]', 'not json'])
def test_bad_file_exits(tmp_path, body):
    f = tmp_path / "s.json"
    f.write_text(body)
    with pytest.raises(SystemExit):
        watch.load_subjects(str(f))
