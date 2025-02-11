from threading import Lock
from typing import OrderedDict
import uuid
from proglog import ProgressBarLogger

BAR_LOCK = Lock()
BAR_DATA = OrderedDict()


class FlaskProgressBarLogger(ProgressBarLogger):
    def __init__(self, **kwargs):
        ProgressBarLogger.__init__(self, **kwargs)
        self.lock = Lock()
        self.task_id = str(uuid.uuid4())

    def bars_callback(self, bar, attr, value, old_value):
        with BAR_LOCK:
            for task_id in BAR_DATA:
                if BAR_DATA[task_id]["total"] <= BAR_DATA[task_id]["index"]:
                    del BAR_DATA[task_id]
            for key, data in self.bars.items():
                BAR_DATA[self.task_id] = {
                    **data,
                    "desc": key,
                    "task_id": self.task_id,
                }


def get_progress_bars():
    with BAR_LOCK:
        return BAR_DATA