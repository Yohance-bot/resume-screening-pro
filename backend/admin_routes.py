import secrets
import string

from flask import Blueprint, jsonify, request
from flask_login import current_user

from auth_models import User
from auth_utils import admin_required, validate_password_policy
from extensions import db

admin_bp = Blueprint('admin', __name__, url_prefix='/api/admin')


def _generate_temp_password(length: int = 12) -> str:
    alphabet = string.ascii_letters + string.digits + "!@#$%^&*()_+-=[]{}|;:,.<>?"
    # Ensure policy-friendly by forcing at least one of each category
    while True:
        pwd = "".join(secrets.choice(alphabet) for _ in range(length))
        ok, _ = validate_password_policy(pwd)
        if ok:
            return pwd


@admin_bp.route('/users', methods=['GET'])
@admin_required
def list_users():
    users = User.query.order_by(User.created_at.desc()).all()
    return jsonify({
        'users': [
            {
                'id': u.id,
                'name': u.name,
                'email': u.email,
                'role': u.role,
                'created_at': u.created_at.isoformat() if u.created_at else None,
                'force_password_change': bool(u.force_password_change),
            }
            for u in users
        ]
    })


@admin_bp.route('/users', methods=['POST'])
@admin_required
def create_user():
    data = request.get_json() or {}
    name = (data.get('name') or '').strip() or None
    email = (data.get('email') or '').strip().lower()
    role = (data.get('role') or 'user').strip().lower()
    initial_password = data.get('password')

    if not email:
        return jsonify({'error': 'Email is required'}), 400

    if not email.endswith('@happiestminds.com'):
        return jsonify({'error': 'Email must end with @happiestminds.com'}), 400

    if role not in ('admin', 'user'):
        return jsonify({'error': 'role must be admin or user'}), 400

    existing = User.query.filter(User.email == email).first()
    if existing:
        return jsonify({'error': 'Email already exists'}), 400

    if initial_password:
        ok, msg = validate_password_policy(initial_password)
        if not ok:
            return jsonify({'error': msg}), 400
    else:
        initial_password = _generate_temp_password()

    user = User(
        name=name,
        email=email,
        username=email,  # so user can login with email immediately
        role=role,
        force_password_change=True,
    )
    user.set_password(initial_password)

    db.session.add(user)
    db.session.commit()

    return jsonify({
        'message': 'User created',
        'user': {
            'id': user.id,
            'name': user.name,
            'email': user.email,
            'role': user.role,
            'created_at': user.created_at.isoformat() if user.created_at else None,
            'force_password_change': bool(user.force_password_change),
        },
        # acceptable for this assignment: return once
        'temporary_password': initial_password,
    })


@admin_bp.route('/users/<int:user_id>/reset-password', methods=['POST'])
@admin_required
def reset_password(user_id: int):
    user = User.query.get(user_id)
    if not user:
        return jsonify({'error': 'User not found'}), 404

    data = request.get_json() or {}
    temp_password = data.get('temporary_password')

    if temp_password:
        ok, msg = validate_password_policy(temp_password)
        if not ok:
            return jsonify({'error': msg}), 400
    else:
        temp_password = _generate_temp_password()

    user.set_password(temp_password)
    user.force_password_change = True
    db.session.commit()

    return jsonify({
        'message': 'Password reset',
        'user': {
            'id': user.id,
            'name': user.name,
            'email': user.email,
            'role': user.role,
            'force_password_change': bool(user.force_password_change),
        },
        'temporary_password': temp_password,
    })


@admin_bp.route('/users/<int:user_id>', methods=['DELETE'])
@admin_required
def delete_user(user_id: int):
    user = User.query.get(user_id)
    if not user:
        return jsonify({'error': 'User not found'}), 404

    if int(user.id) == int(current_user.id):
        return jsonify({'error': 'You cannot delete your own account'}), 400

    if user.role == 'admin':
        admin_count = User.query.filter(User.role == 'admin').count()
        if admin_count <= 1:
            return jsonify({'error': 'Cannot delete the last admin user'}), 400

    db.session.delete(user)
    db.session.commit()

    return jsonify({'message': 'User deleted'})
