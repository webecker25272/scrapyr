from flask_login import UserMixin
from sqlalchemy import create_engine
from scrapyr import db, app, login_manager, engine

#User login lookup
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

#User database table
class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key = True)
    username = db.Column(db.String, unique = True, nullable = False)
    password = db.Column(db.String(60), nullable = False)

    def __repr__(self):
        return f"User('{self.id}','{self.username}')"




