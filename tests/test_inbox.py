import json

from twiddler_tools.inbox import Inbox


def test_add_and_dedupe(tmp_path):
    inbox = Inbox(tmp_path / "inbox.json")
    a = inbox.add("or")
    b = inbox.add("or")
    assert a is b
    assert len(inbox.items()) == 1


def test_add_case_insensitive_dedupe(tmp_path):
    inbox = Inbox(tmp_path / "inbox.json")
    inbox.add("Or")
    assert inbox.find("or") is not None
    assert len(inbox.items()) == 1


def test_mark_exported(tmp_path):
    inbox = Inbox(tmp_path / "inbox.json")
    inbox.add("ing")
    inbox.mark_exported("ing", chord_id="T-:F4L")
    item = inbox.find("ing")
    assert item.status == "exported"
    assert item.chord_id == "T-:F4L"


def test_persistence_round_trip(tmp_path):
    p = tmp_path / "inbox.json"
    inbox = Inbox(p)
    inbox.add("an")
    inbox.add("st")
    reloaded = Inbox(p)
    assert reloaded.find("an") is not None
    assert reloaded.find("st") is not None
    assert len(reloaded.items()) == 2


def test_pending_filter(tmp_path):
    inbox = Inbox(tmp_path / "inbox.json")
    inbox.add("or")
    inbox.add("ing")
    inbox.mark_exported("ing")
    pending = inbox.pending()
    assert [i.text for i in pending] == ["or"]


def test_add_with_chord_id_persists(tmp_path):
    p = tmp_path / "inbox.json"
    inbox = Inbox(p)
    inbox.add("or", chord_id="F2M 3R 4R")
    reloaded = Inbox(p)
    assert reloaded.find("or").chord_id == "F2M 3R 4R"


def test_legacy_added_status_migrates_to_pending(tmp_path):
    p = tmp_path / "inbox.json"
    p.write_text(
        json.dumps(
            {
                "items": [
                    {"text": "or", "status": "added", "chord_id": "F2M 3R 4R"}
                ]
            }
        )
    )
    inbox = Inbox(p)
    item = inbox.find("or")
    assert item.status == "pending"
    assert item.chord_id == "F2M 3R 4R"


def test_update_chord_resets_status(tmp_path):
    inbox = Inbox(tmp_path / "inbox.json")
    inbox.add("or", chord_id="F2M 3R 4R")
    inbox.mark_exported("or")
    assert inbox.find("or").status == "exported"
    inbox.update("or", chord_id="F2M 3R 3M")
    item = inbox.find("or")
    assert item.chord_id == "F2M 3R 3M"
    assert item.status == "pending"


def test_update_renames_text(tmp_path):
    inbox = Inbox(tmp_path / "inbox.json")
    inbox.add("or", chord_id="F2M 3R 4R")
    inbox.update("or", new_text="the", chord_id="F2M 3R 3M")
    assert inbox.find("or") is None
    item = inbox.find("the")
    assert item is not None
    assert item.chord_id == "F2M 3R 3M"


def test_override_persists(tmp_path):
    p = tmp_path / "inbox.json"
    inbox = Inbox(p)
    inbox.add("zz", chord_id="F2M 3R 4R", override=True)
    reloaded = Inbox(p)
    assert reloaded.find("zz").override is True


def test_update_override(tmp_path):
    inbox = Inbox(tmp_path / "inbox.json")
    inbox.add("zz", chord_id="F2M 3R 4R")
    assert inbox.find("zz").override is False
    inbox.update("zz", override=True)
    assert inbox.find("zz").override is True
