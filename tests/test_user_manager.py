import pytest
from pathlib import Path
import tempfile
from Open_Source import UserManager

@pytest.fixture
def tmp_user_file():
    path = Path(tempfile.mkstemp()[1])
    yield path
    path.unlink(missing_ok=True)

def test_add_user_and_get_users(tmp_user_file):
    manager = UserManager(tmp_user_file)
    manager.add_user("100")
    assert "100" in manager.get_users()