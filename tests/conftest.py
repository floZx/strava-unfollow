import pytest
from kudostracker.storage import Storage


@pytest.fixture
def storage():
    s = Storage(":memory:")
    s.init_schema()
    yield s
    s.close()
