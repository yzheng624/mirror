# -*- coding: utf-8 -*-
import os
from flask import Flask
from flask import url_for
from flask import render_template
from flask import request
from flask import redirect
from flask import g
from werkzeug import secure_filename
import nltk
import string
from nltk.stem.porter import PorterStemmer
from nltk.stem import WordNetLemmatizer
from nltk.corpus import wordnet
from database import Database
import cPickle as pickle
import math
from sift import match, SIFT_STORE_LOCATION
from rsift import match as match2
from colors import match as match_color
from spell import Corrector
from images_cluster import find_cluster
from images_cluster import match as match3

UPLOAD_FOLDER = 'static/media'
ALLOWED_EXTENSIONS = set(['txt', 'pdf', 'png', 'jpg', 'jpeg', 'gif'])
DATABASE = 'database.pkl'

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/search', methods=['GET', 'POST'])
def search():
    query = request.form['query'].strip()
    
    corrected_query = _correct_query(query)
    if corrected_query == query:
        corrected_query = None
    
    results, scores = _query_search(query)

    return render_template('result.html', results = results, query = query, scores = scores, corrected_query = corrected_query)


@app.route('/search/<query>')
def search2(query):
    query = query.strip()
    
    corrected_query = _correct_query(query)
    if corrected_query == query:
        corrected_query = None

    results, scores = _query_search(query)
        
    return render_template('result.html', results = results, query = query, scores = scores, corrected_query = corrected_query)

@app.route('/similar', methods=['GET', 'POST'])
def similar():
    if request.method == 'POST':
        file = request.files['image']
        if file and allowed_file(file.filename.lower()):
            filename = secure_filename(file.filename.lower()).lower()
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            fileurl = app.config['UPLOAD_FOLDER'] + '/' + filename
            file_location = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            results = find_cluster(file_location)
            print len(results)
            results, distances = match3( file_location, results )
            results = sorted(results, key = lambda x: -distances[x])
            return render_template('similar.html', results = results, distances = distances, original = fileurl)
    
    return redirect(url_for('index'))

def get_db():
    if not hasattr(g, 'db'):
        g.db = pickle.load(open(DATABASE, 'rb'))
    return g.db

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1] in ALLOWED_EXTENSIONS

def query_preprocess(val):
    stopwords = nltk.corpus.stopwords.words('english')
    stopwords.extend(string.punctuation)
    stopwords = set(stopwords)
    porter = PorterStemmer()
    return [porter.stem(x) for x in val if x not in stopwords and len(x) > 1]

def _query_search(input_query):
    db = get_db()
    results = None

    queries = query_preprocess(input_query.split())
    scores = {}

    for query in queries:
        if not query in db.tags:
            continue
        tag = query
        result = set(db.tags_filenames[tag])

        if results is None:
            results = result
        elif len(result) == 0:
            pass
        else:
            results_new = set.intersection(results, result)
            if len(results_new) == 0:
                for f in result:
                    if scores.has_key(f):
                        scores[f] -= 1
                    else:
                        scores[f] = -1
                results = set.union(results, result)
            else:
                results = results_new

    if results is not None:
        for filename in results:
            if scores.has_key(filename):
                pass
            else:
                scores[filename] = float(len(db.tags)) / float(len(db.filenames)) / math.log(float(db.files_count[filename]))

            for tag in db.filenames_tags[filename]:
                if tag in queries:
                    tag_idf = math.log(float(len(db.filenames)) / float(db.tags_count[tag]))
                    scores[filename] += tag_idf
            constant = float(len(db.tags)) / float(len(db.filenames)) / float(db.files_count[filename])
            scores[filename] *= constant

        results = sorted(results, key=lambda x: -scores[x])
    else:
        results = []

    return results, scores

def _correct_query(query):
    if not hasattr(g, 'corrector'):
        g.correct = Corrector()
    c = g.correct
    corrected_query = ''
    for word in query.split():
        corrected_query = corrected_query + c.correct(word) + ' '
    corrected_query = corrected_query.strip()
    return corrected_query

if __name__ == '__main__':
    app.run(debug=True)
