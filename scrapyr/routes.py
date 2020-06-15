from flask import Flask, render_template
from scrapyr import app

@app.route("/")
def home():
    return 'test'