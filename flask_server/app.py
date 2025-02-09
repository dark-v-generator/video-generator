from flask import Flask, render_template
from flask import Flask, render_template, request, redirect, url_for
from flask_server.helper import build_nested_dict
from services import config_service

app = Flask(__name__)
CONFIG_FILE_PATH = 'new_config.yaml'

@app.route('/')
def home():
    return render_template('index.html')

@app.route("/save_config", methods=["POST"])
def save_config():
    data = build_nested_dict(request.form.to_dict())
    config_service.save_main_config(data, CONFIG_FILE_PATH)
    return redirect(url_for("config_page"))

@app.route("/config", methods=["GET", "POST"])
def config_page():    
    config = config_service.get_main_config(CONFIG_FILE_PATH)
    return render_template("config.html", config=config)

if __name__ == '__main__':
    app.run(debug=True)

