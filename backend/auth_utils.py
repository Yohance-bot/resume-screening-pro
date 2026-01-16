from functools import wraps
import re

from flask import jsonify
from flask_login import current_user


def admin_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not current_user.is_authenticated:
            return jsonify({"error": "Unauthorized"}), 401
        if current_user.role != "admin":
            return jsonify({"error": "Forbidden"}), 403
        return fn(*args, **kwargs)

    return wrapper


def validate_password_policy(password: str):
    if password is None:
        return False, "Password is required"

    if len(password) < 8:
        return False, "Password must be at least 8 characters"

    has_upper = re.search(r"[A-Z]", password) is not None
    has_lower = re.search(r"[a-z]", password) is not None
    has_number = re.search(r"[0-9]", password) is not None
    has_special = re.search(r"[^A-Za-z0-9]", password) is not None

    if not (has_upper and has_lower and has_number and has_special):
        return (
            False,
            "Password must include upper, lower, number, and special character",
        )

    return True, None
