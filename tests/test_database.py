import pytest
from pathlib import Path
import tempfile
from Open_Source import Database

@pytest.fixture
def tmp_db_file():
    path = Path(tempfile.mkstemp()[1])
    yield path
    path.unlink(missing_ok=True)

def test_save_and_load_json(tmp_db_file):
    data = {"key": "value"}
    Database.save_json(tmp_db_file, data)
    result = Database.load_json(tmp_db_file)
    assert result == data