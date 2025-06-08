import pytest
import os
import json
from datetime import datetime, timedelta
import Open_Source  # ✅ импортируем весь модуль

@pytest.fixture
def test_deadlines_file(monkeypatch, tmp_path):
    test_file = tmp_path / "deadlines.json"
    sample = [{
        "deadline_id": 1,
        "title": "Test",
        "subject": "Math",
        "description": "Homework",
        "due_date": (datetime.now() + timedelta(days=2)).isoformat(),
        "is_private": True,
        "created_by_id": 123,
        "created_in_chat": 456,
        "author_name": "Test User"
    }]
    test_file.write_text(json.dumps(sample), encoding="utf-8")
    monkeypatch.setattr("Open_Source.DEADLINES_FILE", str(test_file))
    return test_file

def test_load_deadlines(test_deadlines_file):
    Open_Source.load_deadlines()
    assert len(Open_Source.deadlines) > 0

def test_save_deadlines(test_deadlines_file):
    Open_Source.load_deadlines()
    Open_Source.save_deadlines()
    with open(test_deadlines_file, "r", encoding="utf-8") as f:
        data = json.load(f)
        assert data[0]["title"] == "Test"