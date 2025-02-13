from threading import Thread
from flask import Flask, jsonify, render_template
from flask import Flask, render_template, request, redirect, url_for
from flask_server.helper import build_nested_dict
from services import config_service
from flask_server.progress import (
    clear_progress_bars,
    get_progress_bars,
    FlaskProgressBarLogger,
)
from services import history_service

CONFIG_FILE_PATH = "new_config.yaml"


def static_path(st: str):
    if not "/static/" in st:
        return ''
    return f"/static/{st.split("/static/")[-1]}"


def __get_context():
    return {
        "isinstance": isinstance,
        "int": int,
        "float": float,
        "bool": bool,
        "dict": dict,
        "static_path": static_path,
    }


app = Flask(__name__)

def progress_bar_exists(task_id: str) -> bool:
    bars_info = get_progress_bars()
    return task_id in bars_info and (bars_info[task_id]['index'] < bars_info[task_id]['total'])

@app.route("/")
def home():
    config = config_service.get_main_config(CONFIG_FILE_PATH)
    clear_progress_bars()
    bars_info = get_progress_bars()
    reddit_histories = history_service.list_histories(config)
    return render_template(
        "index.html", 
        reddit_histories=reddit_histories,
        **__get_context(),
        bars_info=bars_info
    )


@app.route("/save_config", methods=["POST"])
def save_config():
    data = build_nested_dict(request.form.to_dict())
    config_service.save_main_config(data, CONFIG_FILE_PATH)
    return redirect(url_for("config_page"))


@app.route("/srcap_reddit_post", methods=["POST"])
def srcap_reddit_post():
    data = build_nested_dict(request.form.to_dict())
    config = config_service.get_main_config(CONFIG_FILE_PATH)
    history_service.srcap_reddit_post(data["url"], config)
    return redirect(url_for("home"))


@app.route("/config")
def config_page():
    config = config_service.get_main_config(CONFIG_FILE_PATH)
    return render_template(
        "config.html",
        **__get_context(),
        config=config.model_dump(),
    )


@app.route("/history/<history_id>")
def history_details(history_id):
    config = config_service.get_main_config(CONFIG_FILE_PATH)
    reddit_history = history_service.get_reddit_history(history_id, config)
    show_loading = request.args.get("show_loading", "false").lower() == "true"
    if not show_loading and progress_bar_exists(reddit_history.id):
        return redirect(url_for("history_details", history_id=history_id, show_loading=True))
    return render_template(
        "history_details.html", reddit_history=reddit_history, show_loading=show_loading, **__get_context()
    )


@app.route("/history/generate-video/<history_id>", methods=["POST"])
def generate_video(history_id):
    config = config_service.get_main_config(CONFIG_FILE_PATH)
    reddit_history = history_service.get_reddit_history(history_id, config)

    data = build_nested_dict(request.form.to_dict())
    low_quality = data.get("low_quality", "")
    low_quality = True if low_quality == "on" else False
    captions = data.get("captions", "")
    captions = True if captions == "on" else False
    speech = data.get("speech", "")
    speech = True if speech == "on" else False
    cover = data.get("cover", "")
    cover = True if cover == "on" else False
    rate = data.get("rate", "1.5")
    rate = float(rate)
    content = data.get('reddit_history', {}).get('history', {}).get('content')
    title = data.get('reddit_history', {}).get('history', {}).get('title')
    gender = data.get('reddit_history', {}).get('history', {}).get('gender')

    if title:
        reddit_history.history.title = title
    if content:
        reddit_history.history.content = content
    if gender:
        reddit_history.history.gender = gender
    history_service.save_reddit_history(reddit_history, config)
    clear_progress_bars()

    def generate_video():
        if speech:
            history_service.generate_speech(reddit_history, rate, config)
        if captions:
            history_service.generate_captions(reddit_history, rate, config)
        if cover:
            history_service.generate_cover(reddit_history, config)
        history_service.generate_reddit_video(
            reddit_history,
            config,
            low_quality=low_quality,
            logger=FlaskProgressBarLogger(task_id=reddit_history.id),
        )

    thread = Thread(target=generate_video)
    thread.start()

    return redirect(url_for("history_details", history_id=history_id, show_loading=True))

@app.route("/history/delete/<history_id>", methods=["POST"])
def delete_reddit_history(history_id):
    config = config_service.get_main_config(CONFIG_FILE_PATH)
    history_service.delete_reddit_history(history_id, config)
    return redirect(url_for('home'))

@app.route("/bars_progress/")
def verify_progress():
    return jsonify(get_progress_bars())


if __name__ == "__main__":
    app.run(debug=True)
