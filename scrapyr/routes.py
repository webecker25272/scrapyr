from flask import Flask, render_template
from scrapyr import app

@app.route("/")
def home():
    return render_template('adhoc.html')