from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required, login_user

from . import bcrypt, login_manager
from .forms import LoginForm
from .models import User, db


@login_manager.user_loader
def load_user(user_id):
    try:
        return User.query.get(user_id)
    except:
        return None


@login_manager.request_loader
def load_user_from_request(request):
    auth_str = request.headers.get('Authorization')
    token = auth_str.split(' ')[1] if auth_str else ''
    if token:
        user_id = User.decode_token(token)
        user = User.query.get(int(user_id))
        if user:
            return user
    return None

@login_manager.unauthorized_handler
def unauthorized():
    flash('You must be logged in to view that page.', 'warning')
    return redirect(url_for('login'))
