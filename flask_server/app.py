import time
from flask import Flask, jsonify, render_template
from flask import Flask, render_template, request, redirect, url_for
from flask_server.helper import build_nested_dict
from services import config_service
from flask_server.progress import ProgressBarLogger, get_progress_bars

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
CONFIG_FILE_PATH = 'new_config.yaml'

@app.route('/')
def home():
    return render_template('index.html')

@app.route("/save_config", methods=["POST"])
def save_config():
    # TODO parse bool fields
    data = build_nested_dict(request.form.to_dict())
    config_service.save_main_config(data, CONFIG_FILE_PATH)
    return redirect(url_for("config_page"))

@app.route("/config", methods=["GET", "POST"])
def config_page():    
    config = config_service.get_main_config(CONFIG_FILE_PATH)
    return render_template(
        "config.html", 
        **__get_context(),
        config=config.model_dump(),
    )

@app.route("/bars_progress/")
def verify_progress():
    return jsonify(get_progress_bars())


if __name__ == '__main__':
    app.run(debug=True)

