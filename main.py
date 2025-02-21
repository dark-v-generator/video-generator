from flask_server import app as flask_server
import socket

def get_local_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.connect(("8.8.8.8", 80))
    ip = s.getsockname()[0]
    s.close()
    return ip

def run_server():
    flask_server.app.run(host='0.0.0.0')


if __name__ == "__main__":
    run_server()
