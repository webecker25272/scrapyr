from flask import Flask, render_template, request, redirect, url_for
from scrapyr import app
from scrapyr.forms import UploadForm
from scrapyr import auth

@app.route('/')
def index():
    return redirect(url_for('adhoc'))

@app.route('/historical')

def historical():
    return 'test'

@app.route('/adhoc', methods = ['GET','POST'])
def adhoc():
    upload_form = UploadForm()
    if request.method == 'POST':
        f = upload_form.excel_file.data
        #excel_file = read_excel(f, header=None)
        bool_commit = upload_form.bool_commit.data
        #generate_tabnonsum(excel_file, bool_commit)
        #generate_tabsum(bool_commit)
        #adhoc_dictionary = word_dicts(boolHistorical=False)
        #divAtRisk = graph_at_risk(boolHistorical=False)
        #divTW = graph_this_week(boolHistorical=False)
        #divNW = graph_next_week(boolHistorical=False)
        temp_exists = True
        #if bool_commit == True:
        #    return 'Successfully written to prod with as of date {}'.format(adhoc_dictionary['as_of_date'])
        #drop temp tables
        #return render_template('report.html', **adhoc_dictionary, divAtRisk = divAtRisk, divTW = divTW, divNW = divNW, temp_exists = temp_exists)
    return render_template('adhoc.html', upload_form = upload_form)