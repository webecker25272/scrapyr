from datetime import date
import os
from flask import flash, jsonify, redirect, render_template, request, session, url_for, send_file
from flask_login import current_user, login_required, login_user, logout_user
from pandas import read_excel
from werkzeug.utils import secure_filename
from scrapyr import app, bcrypt, db, login_manager
from scrapyr.forms import LoginForm, UploadForm
from scrapyr import User
from scrapyr.processing import generate_tabnonsum, generate_tabsum, write_to_excel, word_dicts, graph_at_risk, graph_this_week, graph_next_week


@app.route('/')
def index():
    return redirect(url_for('login'))


@app.route('/login', methods = ['GET','POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('historical'))

    login_form = LoginForm()
    if login_form.validate_on_submit():
        user = User.query.filter_by(username = login_form.username.data).first()
        if user and bcrypt.check_password_hash(user.password, login_form.password.data):
            login_user(user)
            print(current_user.username)
            next_page = request.args.get('next')
            flash('Logged in!', 'success')
            return redirect(next_page or url_for('historical'))
        else:
            flash('Invalid username/password combination', 'danger')
            return redirect(url_for('login'))
    return render_template('login.html', login_form = login_form)


@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('login'))
    

@app.route('/historical')
@login_required
def historical():
    word_dictionary = word_dicts(boolHistorical=True)
    divAtRisk = graph_at_risk(boolHistorical=True)
    divTW = graph_this_week(boolHistorical=True)
    divNW = graph_next_week(boolHistorical=True)
    return render_template('report.html', **word_dictionary, divAtRisk = divAtRisk, divTW = divTW, divNW = divNW)


@app.route('/adhoc', methods = ['GET','POST'])
def adhoc():
    upload_form = UploadForm()
    if request.method == 'POST':
        f = upload_form.excel_file.data
        excel_file = read_excel(f, header=None)
        bool_commit = upload_form.bool_commit.data
        generate_tabnonsum(excel_file, bool_commit)
        generate_tabsum(bool_commit)
        adhoc_dictionary = word_dicts(boolHistorical=False)
        divAtRisk = graph_at_risk(boolHistorical=False)
        divTW = graph_this_week(boolHistorical=False)
        divNW = graph_next_week(boolHistorical=False)
        temp_exists = True
        if bool_commit == True:
            return 'Successfully written to prod with as of date {}'.format(adhoc_dictionary['as_of_date'])
        #drop temp tables
        return render_template('report.html', **adhoc_dictionary, divAtRisk = divAtRisk, divTW = divTW, divNW = divNW, temp_exists = temp_exists)
    return render_template('adhoc.html', upload_form = upload_form)


@app.route('/export')
def export():
    output = write_to_excel()
    return send_file(output, attachment_filename = 'Invoice Data ' + str(date.today()) + '.xlsx', as_attachment = True)
