from threading import Lock
from typing import OrderedDict
import uuid
from proglog import ProgressBarLogger

BAR_LOCK = Lock()
BAR_DATA = OrderedDict()


class FlaskProgressBarLogger(ProgressBarLogger):
    def __init__(self, task_id=str(uuid.uuid4()), **kwargs):
        ProgressBarLogger.__init__(self, **kwargs)
        self.lock = Lock()
        self.task_id = task_id

    def __update_attr(self, attr, total):
        with BAR_LOCK:
            if not self.task_id in BAR_DATA:
                BAR_DATA[self.task_id] = { 'total': 0, 'index': 0, 'message': ''}
            BAR_DATA[self.task_id][attr] = total
            
    def bars_callback(self, bar, attr, value, old_value):
        if attr == 'total' or attr == 'index':
            self.__update_attr(value)
        else:
            print(bar, attr, value, old_value)


def get_progress_bars():
    with BAR_LOCK:
        return BAR_DATA
