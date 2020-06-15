from scrapyr.models import User
from flask import Flask
from flask_bcrypt import Bcrypt
from flask_login import LoginManager
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import create_engine
import os

basedir = os.path.abspath(os.path.dirname(__file__))
app = Flask(__name__)

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

#User login lookup
@login_manager.user_loader
def load_user(user_name):
    return User.query.get(user_name)
    #return User.query.get(int(user_id))

from scrapyr import routes