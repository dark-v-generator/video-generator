import threading
import queue
from typing import Dict
import uuid
from threading import Lock
import time


class WorkerJob(threading.Thread):
    def __init__(self, id=None, *args, **kwargs):
        self.id = str(uuid.uuid4()) if id is None else id
        super().__init__(*args, **kwargs)


class Worker(threading.Thread):
    def __init__(
        self, no_task_wait=60, max_parallel=3, wait_for_new_job=5, *args, **kwargs
    ):
        self.q = queue.Queue()
        self.dict_lock = Lock()
        self.no_task_wait = no_task_wait
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
        with self.dict_lock:
            if len(self.running_threads) < self.max_parallel:
                job: WorkerJob = self.q.get(timeout=self.wait_for_new_job)
                del self.waiting_threads[job.id]
                self.running_threads[job.id] = job
                self.q.task_done()
                job.start()
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
            print('worker loop')
            try:
                if not self.start_next_job():
                    time.sleep(self.wait_for_new_job)
                    self.clean_finished_jobs()
            except queue.Empty:
                time.sleep(self.no_task_wait)
