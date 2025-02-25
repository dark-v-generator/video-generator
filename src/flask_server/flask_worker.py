import os
from threading import Lock
from typing import Dict
from flask import Flask
from src.flask_server.worker import Worker
from src.flask_server.progress import FlaskProgressBarLogger


class FlaskWorker(Flask):
    worker = Worker()
    progress_bars: Dict[str, FlaskProgressBarLogger] = {}
    progress_bars_lock = Lock()

    def create_progress_bar(self, bar_logger: FlaskProgressBarLogger):
        with self.progress_bars_lock:
            self.progress_bars[bar_logger.task_id] = bar_logger

    def get_bars_data(self) -> dict:
        with self.progress_bars_lock:
            return {task_id:data.model_dump() for task_id, data in self.progress_bars.items()}

    def get_tasks_status(self):
        tasks_status = self.worker.get_status()
        bars_data = self.get_bars_data()
        response = {}
        for task_id, status in tasks_status.items():
            bar_data: dict = bars_data.get(task_id, {})
            progress_message: str = bar_data.get("message", "")
            message = ""
            if progress_message:
                message = progress_message
            elif status == "on_queue":
                message = "Na fila para ser processado..."
            elif status == "running":
                message = "Processando..."
            response[task_id] = {
                **bar_data,
                "message": message,
            }
        return response

    def task_exists(self, task_id):
        tasks_status = self.worker.get_status()
        return task_id in tasks_status

    def run(self, host=None, port=None, debug=None, load_dotenv=True, **options):
        if not self.debug or os.getenv("WERKZEUG_RUN_MAIN") == "true":
            with self.app_context():
                print("Starting worker")
                self.worker.start()
        super(FlaskWorker, self).run(
            host=host, port=port, debug=debug, load_dotenv=load_dotenv, **options
        )
