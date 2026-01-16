from flask import Flask, jsonify, request
from flask_cors import CORS
from flask_login import LoginManager
import os

app = Flask(__name__)
app.secret_key = 'test-secret-key'

# Configure CORS correctly
CORS(app,
     supports_credentials=True,
     origins=["http://localhost:5173"],
     allow_headers=["Content-Type"],
     methods=["GET","POST","PUT","DELETE","OPTIONS"])

# Setup Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'auth.login'

# Add unauthorized handler to prevent redirects for API routes
@login_manager.unauthorized_handler
def unauthorized():
    # Check if the request is for an API endpoint
    if request.path.startswith('/api/'):
        return jsonify({"error": "Unauthorized"}), 401
    # For non-API routes, let Flask-Login handle the redirect normally
    return login_manager.unauthorized()

# Mock user loader
@login_manager.user_loader
def load_user(user_id):
    return None

@app.route('/api/auth/me')
def me():
    return jsonify({"authenticated": False})

@app.route('/health')
def health():
    return jsonify({"status": "healthy"})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5050, debug=True)
