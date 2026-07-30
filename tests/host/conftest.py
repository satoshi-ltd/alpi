from __future__ import annotations

import pytest

from alpi.host import device_state as _device_state


@pytest.fixture(autouse=True)
def _fresh_summary_cache():
    _device_state.invalidate_summary()
    yield
    _device_state.invalidate_summary()
