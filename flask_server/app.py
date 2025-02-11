import time
from flask import Flask, jsonify, render_template
from flask import Flask, render_template, request, redirect, url_for
from flask_server.helper import build_nested_dict
from services import config_service
from flask_server.progress import ProgressBarLogger, get_progress_bars
from services import history_service

CONFIG_FILE_PATH = 'new_config.yaml'

def sample_processing_task(logger: ProgressBarLogger):
    for _ in logger.iter_bar(idx=range(1, 101)):
        time.sleep(0.1)


def __get_context():
    return {
        "isinstance": isinstance,
        "int": int,
        "float": float,
        "bool": bool,
        "dict": dict,
        "bars_info": get_progress_bars()
    }

app = Flask(__name__)

@app.route('/')
def home():
    config = config_service.get_main_config(CONFIG_FILE_PATH)
    reddit_videos = history_service.list_histories(config)
    return render_template('index.html', reddit_videos=reddit_videos)

@app.route("/save_config", methods=["POST"])
def save_config():
    data = build_nested_dict(request.form.to_dict())
    config_service.save_main_config(data, CONFIG_FILE_PATH)
    return redirect(url_for("config_page"))

@app.route("/srcap_reddit_post", methods=["POST"])
def srcap_reddit_post():
    data = build_nested_dict(request.form.to_dict())
    config = config_service.get_main_config(CONFIG_FILE_PATH)
    history_service.srcap_reddit_post(data['url'], config)
    return redirect(url_for("home"))

@app.route("/config", methods=["GET", "POST"])
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
    return render_template("history_details.html", reddit_history=reddit_history)

@app.route("/history/generate-cover/<history_id>", methods=["POST"])
def generate_cover(history_id):
    config = config_service.get_main_config(CONFIG_FILE_PATH)
    reddit_history = history_service.get_reddit_history(history_id, config)
    history_service.generate_cover(reddit_history, config)
    return redirect(url_for("history_details", history_id=history_id))

@app.route("/bars_progress/")
def verify_progress():
    return jsonify(get_progress_bars())


if __name__ == '__main__':
    app.run(debug=True)

