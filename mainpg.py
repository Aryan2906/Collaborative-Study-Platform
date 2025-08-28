from flask import Flask
from main import app as application
app = Flask(__name__)
@app.route("/")
def hello_world():
    return "<p>Hello Chicago!</p>"