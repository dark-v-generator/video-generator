import tempfile
import uuid
from flask import json
from proglog import ProgressBarLogger

class FlaskProgressBarLogger(ProgressBarLogger):
    def __init__(self, task_id=str(uuid.uuid4()), **kwargs):
        ProgressBarLogger.__init__(self, **kwargs)
        self.task_id = task_id
        self.log_file_name = tempfile.mktemp()
        self.bar_info = {"total": 0, "index": 0, "message": ""}
        self.__update_data()

    def __update_data(self):
        with open(self.log_file_name, 'w') as f:
            f.write(json.dumps(self.bar_info))
    
    def __get_data(self):
        with open(self.log_file_name) as f:
            return json.loads(f.read())

    def __update_attr(self, attr: str, value: str):
        self.bar_info[attr] = value
        self.__update_data()

    def log_message(self, message: str) -> None:
        self.__update_attr("message", message)

    def bars_callback(self, bar, attr, value, old_value):
        if attr == "total" or attr == "index":
            self.__update_attr(attr, value)
    
    def model_dump(self) -> dict:
        return self.__get_data()
