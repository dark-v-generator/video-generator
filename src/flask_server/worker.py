import os
from flask import Flask
from queue import Queue
import threading
import uuid
import time
from typing import Dict
from multiprocessing import Process
from multiprocessing import Lock


class WorkerJob(Process):
    def __init__(self, id=None, *args, **kwargs):
        self.id = str(uuid.uuid4()) if id is None else id
        super().__init__(*args, **kwargs)


class Worker(threading.Thread):
    def __init__(self, max_parallel=3, wait_for_new_job=1, *args, **kwargs):
        self.q = Queue()
        self.dict_lock = Lock()
        self.max_parallel = max_parallel
        self.wait_for_new_job = wait_for_new_job
        self.running_threads: Dict[str, WorkerJob] = {}
        self.waiting_threads: Dict[str, WorkerJob] = {}
        super().__init__(*args, **kwargs)

    def put(self, job: WorkerJob) -> None:
        with self.dict_lock:
            self.waiting_threads[job.id] = job
            self.q.put(job)

    def start_next_job(self) -> bool:
        if self.q.empty():
            return False
        with self.dict_lock:
            if len(self.running_threads) < self.max_parallel:
                job: WorkerJob = self.q.get(timeout=self.wait_for_new_job)
                if job.id in self.running_threads:
                    old_job = self.running_threads[job.id]
                    old_job.terminate()
                    old_job.join()
                    del self.running_threads[old_job.id]
                if job.id in self.waiting_threads:
                    del self.waiting_threads[job.id]
                self.running_threads[job.id] = job
                job.start()
                self.q.task_done()
                return True
        return False

    def get_status(self):
        with self.dict_lock:
            return {
                **{id: "on_queue" for id in self.waiting_threads.keys()},
                **{id: "running" for id in self.running_threads.keys()},
            }

    def clean_finished_jobs(self):
        with self.dict_lock:
            finished_ids = [
                job.id for job in self.running_threads.values() if not job.is_alive()
            ]
            for id in finished_ids:
                self.running_threads[id].join()
                del self.running_threads[id]

    def run(self):
        while True:
            self.clean_finished_jobs()
            if not self.start_next_job():
                time.sleep(self.wait_for_new_job)


class FlaskWorker(Flask):
    worker = Worker()

    def run(self, host=None, port=None, debug=None, load_dotenv=True, **options):
        if not self.debug or os.getenv("WERKZEUG_RUN_MAIN") == "true":
            with self.app_context():
                print("Starting worker")
                self.worker.start()
        super(FlaskWorker, self).run(
            host=host, port=port, debug=debug, load_dotenv=load_dotenv, **options
        )
