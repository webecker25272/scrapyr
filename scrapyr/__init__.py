from flask import Flask
from flask_bcrypt import Bcrypt
from flask_login import LoginManager, UserMixin
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import create_engine
import os

basedir = os.path.abspath(os.path.dirname(__file__))
app = Flask(__name__)

# Config
app.config['CSRF_ENABLED'] = True
app.config['CSRF_SESSION_KEY'] = '\xf3_\xa6(83\x00\x85X\x07V\xe5z\x98e\x7ff\x82-6$\x9d\xd5\xd0'
app.config['SECRET_KEY'] = '\xf3_\xa6(83\x00\x85X\x07V\xe5z\x98e\x7ff\x82-6$\x9d\xd5\xd0'

# SQL Alchemy
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'site.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)
engine = create_engine(app.config['SQLALCHEMY_DATABASE_URI'], connect_args={'check_same_thread': False}, echo = False)
conn = engine.connect()

#Login
bcrypt = Bcrypt(app)
login_manager = LoginManager(app)
login_manager.init_app(app)

#User database table
class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key = True)
    username = db.Column(db.String, unique = True, nullable = False)
    password = db.Column(db.String(60), nullable = False)

    def __repr__(self):
        return f"User('{self.id}','{self.username}')"

#User login lookup
@login_manager.user_loader
def load_user(user_name):
    return User.query.get(user_name)
    #return User.query.get(int(user_id))

from scrapyr import routes