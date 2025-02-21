import os
from flask import jsonify, render_template
from flask import render_template, request, redirect, url_for
from flask_server.entities import GenerateVideoRequest, ScrapRedditPostRequest
from services import config_service
from flask_server.progress import (
    get_progress_bars,
    FlaskProgressBarLogger,
)
from services import history_service
from flask_server.worker import FlaskWorker, WorkerJob

CONFIG_FILE_PATH = "config.yaml"


app = FlaskWorker(__name__)


def static_path(st: str):
    if not "/static/" in st:
        return ""
    return f"/static/{st.split("/static/")[-1]}"


def __get_context():
    return {
        "isinstance": isinstance,
        "int": int,
        "float": float,
        "bool": bool,
        "dict": dict,
        "static_path": static_path,
        "enumerate": enumerate,
        "round": round,
    }


def get_tasks_status():
    worker_status = app.worker.get_status()
    response = worker_status
    progress_bars = get_progress_bars()
    for worker_id in worker_status.keys():
        response[worker_id] = {
            **progress_bars.get(worker_id, {}),
            "queue_status": response.get(worker_id),
        }
    return response


def progress_bar_exists(task_id: str) -> bool:
    tasks_status = get_tasks_status()
    return task_id in tasks_status


@app.route("/")
def home():
    config = config_service.get_main_config(CONFIG_FILE_PATH)
    reddit_histories = history_service.list_histories(config)
    tasks_status = get_tasks_status()
    return render_template(
        "index.html",
        reddit_histories=reddit_histories,
        **__get_context(),
        tasks_status=tasks_status,
    )


@app.route("/srcap_reddit_post", methods=["POST"])
def srcap_reddit_post():
    req = ScrapRedditPostRequest(request.form)
    config = config_service.get_main_config(CONFIG_FILE_PATH)
    reddit_history = history_service.srcap_reddit_post(req.url, req.enhance_history, config)

    if req.number_of_parts > 1:
        history_service.split_reddit_history(reddit_history, config, req.number_of_parts)
    return redirect(url_for("home"))


@app.route("/history/<history_id>")
def history_details(history_id):
    config = config_service.get_main_config(CONFIG_FILE_PATH)
    reddit_history = history_service.get_reddit_history(history_id, config)
    show_loading = request.args.get("show_loading", "false").lower() == "true"
    if not show_loading and progress_bar_exists(reddit_history.id):
        return redirect(
            url_for("history_details", history_id=history_id, show_loading=True)
        )
    return render_template(
        "history_details.html",
        reddit_history=reddit_history,
        show_loading=show_loading,
        **__get_context(),
    )


@app.route("/history/generate-video/<history_id>", methods=["POST"])
def generate_video(history_id):
    config = config_service.get_main_config(CONFIG_FILE_PATH)
    reddit_history = history_service.get_reddit_history(history_id, config)
    req = GenerateVideoRequest(request.form)
    def generate_video():
        if req.speech:
            history_service.generate_speech(reddit_history, req.rate, config)
        if req.captions:
            history_service.generate_captions(
                reddit_history, 
                req.rate, 
                config, 
                enhance_captions=req.enhance_captions
            )
        if req.cover:
            history_service.generate_cover(reddit_history, config)
        history_service.generate_reddit_video(
            reddit_history,
            config,
            low_quality=req.low_quality,
            logger=FlaskProgressBarLogger(task_id=reddit_history.id),
        )

    app.worker.put(WorkerJob(id=reddit_history.id, target=generate_video))

    return redirect(url_for("home"))


@app.route("/history/delete/<history_id>", methods=["POST"])
def delete_reddit_history(history_id):
    config = config_service.get_main_config(CONFIG_FILE_PATH)
    history_service.delete_reddit_history(history_id, config)
    return redirect(url_for("home"))


@app.route("/bars_progress/")
def verify_progress():
    return jsonify(get_tasks_status())


if __name__ == "__main__":
    app.run(debug=True)
