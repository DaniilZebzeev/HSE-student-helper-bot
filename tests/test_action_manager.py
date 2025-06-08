import pytest
from pathlib import Path
import tempfile
from Open_Source import ActionManager

@pytest.fixture
def tmp_action_file():
    path = Path(tempfile.mkstemp()[1])
    yield path
    path.unlink(missing_ok=True)

def test_can_perform_action_initially(tmp_action_file):
    manager = ActionManager(tmp_action_file)
    assert manager.can_perform_action("user1", "beer")

def test_update_and_block_action(tmp_action_file):
    manager = ActionManager(tmp_action_file)
    user_id = "user1"
    action = "beer"
    manager.update_action_time(user_id, action)
    assert not manager.can_perform_action(user_id, action)