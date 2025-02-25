from threading import Lock
from flask import jsonify, render_template
from flask import render_template, request, redirect, url_for
from src.flask_server.entities import (
    DivideHistoryRequest,
    GenerateVideoRequest,
    ScrapRedditPostRequest,
)
from src.services import config_service
from src.flask_server.progress import (
    FlaskProgressBarLogger,
)
from src.services import history_service
from src.flask_server.worker import WorkerJob
from src.flask_server.flask_worker import FlaskWorker

CONFIG_FILE_PATH = "config/base.yaml"

app = FlaskWorker(
    __name__, 
    static_folder="../../web/static/", 
    template_folder="../../web/templates/"
)


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


@app.route("/")
def home():
    config = config_service.get_main_config(CONFIG_FILE_PATH)
    reddit_histories = history_service.list_histories(config)
    tasks_status = app.get_tasks_status()
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
    history_service.srcap_reddit_post(
        req.url, req.enhance_history, config, req.language
    )
    return redirect(url_for("home"))


@app.route("/history/<history_id>")
def history_details(history_id):
    config = config_service.get_main_config(CONFIG_FILE_PATH)
    reddit_history = history_service.get_reddit_history(history_id, config)
    show_loading = request.args.get("show_loading", "false").lower() == "true"
    if not show_loading and app.task_exists(reddit_history.id):
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
    history = reddit_history.history
    if req.title:
        history.title = req.title
    if req.content:
        history.content = req.content
    if req.gender:
        history.gender = req.gender
    reddit_history.history = history
    history_service.save_reddit_history(reddit_history, config)
    def generate_video():
        bar_logger = FlaskProgressBarLogger(task_id=reddit_history.id)
        app.create_progress_bar(bar_logger)
        if req.speech:
            bar_logger.log_message("Generating speech...")
            history_service.generate_speech(reddit_history, req.rate, config)
        if req.captions:
            bar_logger.log_message("Generating captions...")
            history_service.generate_captions(
                reddit_history, req.rate, config, enhance_captions=req.enhance_captions
            )
        if req.cover:
            bar_logger.log_message("Generating cover...")
            history_service.generate_cover(reddit_history, config)
        bar_logger.log_message("Generating video...")
        history_service.generate_reddit_video(
            reddit_history,
            config,
            low_quality=req.low_quality,
            logger=bar_logger,
        )

    app.worker.put(WorkerJob(id=reddit_history.id, target=generate_video))

    return redirect(url_for("home"))


@app.route("/history/divide/<history_id>", methods=["POST"])
def divide_history(history_id):
    req = DivideHistoryRequest(request.form)
    config = config_service.get_main_config(CONFIG_FILE_PATH)
    reddit_history = history_service.get_reddit_history(history_id, config)
    history_service.divide_reddit_history(reddit_history, config, req.number_of_parts)
    return redirect(url_for("home"))


@app.route("/history/delete/<history_id>", methods=["POST"])
def delete_reddit_history(history_id):
    config = config_service.get_main_config(CONFIG_FILE_PATH)
    history_service.delete_reddit_history(history_id, config)
    return redirect(url_for("home"))


@app.route("/bars_progress/")
def verify_progress():
    return jsonify(app.get_tasks_status())


if __name__ == "__main__":
    app.run(debug=True)
