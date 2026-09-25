"""Discovery must stay usable without the video stack (SC-007).

Run in a fresh interpreter: inside pytest the heavy modules may already be
loaded by other tests, which would hide a stray import.
"""

import subprocess
import sys
import time

HEAVY_MODULES = ("moviepy", "whisper", "torch", "playwright")

PROBE = (
    "import sys, src.capabilities.discovery; "
    "print('\\n'.join(sorted({name.split('.')[0] for name in sys.modules})))"
)


def test_importing_discovery_does_not_load_the_video_stack():
    started = time.monotonic()
    result = subprocess.run(
        [sys.executable, "-c", PROBE],
        capture_output=True,
        text=True,
        check=True,
    )
    elapsed = time.monotonic() - started

    loaded = set(result.stdout.split())
    assert loaded.isdisjoint(HEAVY_MODULES), sorted(loaded & set(HEAVY_MODULES))
    assert elapsed < 2.0, f"import took {elapsed:.2f}s"
