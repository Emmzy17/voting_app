from functools import wraps
import os
import hashlib
from textwrap import wrap
from typing import Collection
from winreg import EnableReflectionKey
import pytz
from datetime import datetime
from flask import *
from flask_bootstrap import  Bootstrap
from dotenv import load_dotenv
from faunadb import query as q
from faunadb.objects import Ref
from faunadb.client import FaunaClient

load_dotenv()
client =FaunaClient(secret=os.getenv('API_KEY'), domain='db.us.fauna.com', scheme='https')
indexes = client.query(q.paginate(q.indexes()))
#print(indexes)

app = Flask(__name__)
Bootstrap(app)

def login_required(f):
    @wrap(f)
    def decorator(*args, **kwargs):
        if 'user' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorator

@app.route('/')
def hello():
    return 'hello world'

@app.route('/register', methods=['POST', 'GET'])
def register():
    if request.method == 'POST':
        username = request.form.get('username').strip().lower()
        password = request.form.get('password')

        try:
            user = client.query(q.get(q.match(q.index('user_index', username))))
            flash('The account you are trying to creeate already exists', 'info')
        except:
            user = client.query(q.create(q.collection('users',
                {
                    'data' : {
                        'username' : username,
                        'password' : hashlib.sha512(password.encode()).hexdigest(),
                        'date' : datetime.now(pytz.UTC)
                    }
                }
            )))
            flash('You have created your account, you can create online election ')
            return redirect(url_for('register'))
    return render_template('register.html')


@app.route('/login', methods=['POST', 'GET'])
def register():
    if 'user' in session:
        return redirect(url_for('dashboard'))
    if request.method == 'POST':
        username = request.form.get('username').strip().lower()
        password = request.form.get('password')

        try:
            user = client.query(q.get(q.match('user_index', username)))
            if hashlib.sha512(password.encode().hexdigest()) == user['data']['password']:
                session['user'] = {
                    'id':user['ref'].id(),
                    'username' : user['data']['username']
                }
                return redirect(url_for('dashboard'))
            else:
                raise Exception()

        except:
            flash('You have supplied ivalid login creditentials, please try again')
            return redirect(url_for('login'))
    return render_template('login.html')

@app.route('/dashboard', methods = ['POST', 'GET'])
@login_required
def dashboard():
    elections = client.query(q.paginate(q.match(q.index('election_index'), session['user']['id'])))
    elections_ref = []

    for i in elections['data']:
        elections_ref.append(q.get(q.ref(q.collection('elections'), i.id())))
    return render_template('view-elections.html', elections = client.query(elections_ref))

@app.route('dashboard/create-election', methods = ['POST', 'GET'])
@login_required
def create_election():
    if request.method == 'POST':
        title = request.form.get('title').strip()
        voting_options = request.form.get('voting-options')
        
        options = {}
        for i in voting_options.split('\n'):
            options[i.strip()] = 0
        election = client.query(q.create(q.collection('elections'), {
            'data': {
                'creator':session['user']['id'], 
                'title' : session['user']['title'],
                'voting_options': options,
                'date': datetime.datetime(pytz.UTC)
            }
        }))
        return redirect(url_for('vote', election_id = election['ref'].id()))
    return render_template('create_election.html')

@app.route('/election/<int:election_id>', methods = ['POST', 'GET'])
def vote(election_id):
    try:
        election = client.query(q.get(q.Ref(q.Collection('elections'), election_id)))
    except:
        abort(404)
    if request.method == 'POST':
        vote = request.form.get('vote').strip()
        election['data']['voting_options'][vote] +=1
        client.query(q.update(q.ref(q.collection('elections', election_id), {
            'data' : {
                'voting_option': election['data']['votin_options'], 
            }
            
        })))
        flash('Your vote was successfully recorded', 'sucess')
        return redirect(url_for('vote', election_id = election_id))
    return render_template('vote.html', election['data'])

if __name__ == '__main__':
    app.run(debug=True)

