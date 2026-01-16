from datetime import datetime
import re

from flask import Blueprint, jsonify, request
from flask_login import current_user, login_required, login_user, logout_user
from extensions import db, login_manager
from auth_models import User
from auth_utils import validate_password_policy

# Create auth blueprint
auth_bp = Blueprint('auth', __name__, url_prefix='/api/auth')

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

@auth_bp.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    identifier = (data or {}).get('email')
    password = (data or {}).get('password')
    
    if not identifier or not password:
        return jsonify({'error': 'Email and password are required'}), 400

    user = (
        User.query.filter((User.email == identifier) | (User.username == identifier))
        .limit(1)
        .first()
    )

    if user and user.verify_password(password):
        user.last_login = datetime.utcnow()
        db.session.commit()
        login_user(user)
        return jsonify({
            'message': 'Login successful',
            'user': user.to_dict()
        })
    else:
        return jsonify({'error': 'Invalid credentials'}), 401

@auth_bp.route('/logout', methods=['POST'])
def logout():
    logout_user()
    return jsonify({'message': 'Logout successful'})

@auth_bp.route('/me', methods=['GET'])
def get_current_user():
    if not current_user.is_authenticated:
        return jsonify({'authenticated': False, 'user': None})
    return jsonify({'authenticated': True, 'user': current_user.to_dict()})


@auth_bp.route('/profile', methods=['GET'])
@login_required
def profile():
    return jsonify({'user': current_user.to_dict()})


@auth_bp.route('/profile', methods=['PUT'])
@login_required
def update_profile():
    data = request.get_json() or {}
    name = (data.get('name') or '').strip() or None
    email = (data.get('email') or '').strip().lower() or None

    if email:
        if not re.match(r'^[^@\s]+@[^@\s]+\.[^@\s]+$', email):
            return jsonify({'error': 'Invalid email format'}), 400
        if not email.endswith('@happiestminds.com'):
            return jsonify({'error': 'Email must end with @happiestminds.com'}), 400

        existing = User.query.filter(User.email == email, User.id != current_user.id).first()
        if existing:
            return jsonify({'error': 'Email already exists'}), 400

    user = User.query.get(int(current_user.get_id()))
    if not user:
        return jsonify({'error': 'User not found'}), 404

    user.name = name
    if email:
        user.email = email
        # Keep username aligned so email-login continues to work
        user.username = email

    db.session.commit()
    return jsonify({'message': 'Profile updated', 'user': user.to_dict()})


@auth_bp.route('/change-password', methods=['POST'])
@login_required
def change_password():
    data = request.get_json() or {}
    current_password = data.get('current_password')
    new_password = data.get('new_password')

    if not current_password or not new_password:
        return jsonify({'error': 'current_password and new_password are required'}), 400

    user = User.query.get(int(current_user.get_id()))
    if not user or not user.verify_password(current_password):
        return jsonify({'error': 'Current password is incorrect'}), 400

    ok, msg = validate_password_policy(new_password)
    if not ok:
        return jsonify({'error': msg}), 400

    user.set_password(new_password)
    user.force_password_change = False
    db.session.commit()

    return jsonify({'message': 'Password changed successfully', 'user': user.to_dict()})
