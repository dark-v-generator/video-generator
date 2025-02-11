from threading import Thread
from flask import Flask, jsonify, render_template
from flask import Flask, render_template, request, redirect, url_for
from flask_server.helper import build_nested_dict
from services import config_service
from flask_server.progress import get_progress_bars, FlaskProgressBarLogger
from services import history_service

CONFIG_FILE_PATH = 'new_config.yaml'

def static_path(st: str):
    xs = st.split('/static/')
    if len(xs)==0:
        return ''
    return f'/static/{xs[-1]}'

def __get_context():
    return {
        "isinstance": isinstance,
        "int": int,
        "float": float,
        "bool": bool,
        "dict": dict,
        "bars_info": get_progress_bars(),
        "static_path": static_path
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
    return render_template("history_details.html", reddit_history=reddit_history, **__get_context())

@app.route("/history/generate-cover/<history_id>", methods=["POST"])
def generate_cover(history_id):
    config = config_service.get_main_config(CONFIG_FILE_PATH)
    reddit_history = history_service.get_reddit_history(history_id, config)
    history_service.generate_cover(reddit_history, config)
    return redirect(url_for("history_details", history_id=history_id))

@app.route("/history/generate-speech/<history_id>", methods=["POST"])
def generate_speech(history_id):
    config = config_service.get_main_config(CONFIG_FILE_PATH)
    reddit_history = history_service.get_reddit_history(history_id, config)
    history_service.generate_speech(reddit_history, 1.5, config)
    return redirect(url_for("history_details", history_id=history_id))

@app.route("/history/generate-captions/<history_id>", methods=["POST"])
def generate_captions(history_id):
    config = config_service.get_main_config(CONFIG_FILE_PATH)
    reddit_history = history_service.get_reddit_history(history_id, config)
    history_service.generate_captions(reddit_history, 1.5, config)
    return redirect(url_for("history_details", history_id=history_id))

@app.route("/history/generate-video/<history_id>", methods=["POST"])
def generate_video(history_id):
    config = config_service.get_main_config(CONFIG_FILE_PATH)
    reddit_history = history_service.get_reddit_history(history_id, config)
    def generate_video():
        history_service.generate_reddit_video(reddit_history, config, low_quality=True, logger=FlaskProgressBarLogger())
    thread = Thread(target=generate_video)
    thread.start()
    
    return redirect(url_for("history_details", history_id=history_id))


@app.route("/bars_progress/")
def verify_progress():
    return jsonify(get_progress_bars())


if __name__ == '__main__':
    app.run(debug=True)

