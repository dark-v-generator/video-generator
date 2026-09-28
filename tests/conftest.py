import os

import pytest

# Some tests import litellm before any src module that sets this: keep the
# suite offline and fast whatever the collection order.
os.environ.setdefault("LITELLM_LOCAL_MODEL_COST_MAP", "True")


def pytest_addoption(parser):
    parser.addoption(
        "--update-golden",
        action="store_true",
        default=False,
        help="Rewrite tests/fixtures/*golden*.json from the current behaviour "
        "instead of comparing against it. Review the diff before committing.",
    )


@pytest.fixture
def update_golden(request) -> bool:
    return request.config.getoption("--update-golden")
