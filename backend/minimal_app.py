from flask import Flask, jsonify, request
from flask_cors import CORS
from flask_login import LoginManager
from werkzeug.security import generate_password_hash
import os

# Import shared extensions
from extensions import db, login_manager
from auth_routes import auth_bp
from auth_models import User

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', 'dev-secret-key')

# Configure CORS correctly
CORS(app,
     supports_credentials=True,
     origins=["http://localhost:5173"],
     allow_headers=["Content-Type"],
     methods=["GET","POST","PUT","DELETE","OPTIONS"])

# DB config
basedir = os.path.abspath(os.path.dirname(__file__))
app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{os.path.join(basedir, "resume_screening.db")}'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Initialize shared extensions
db.init_app(app)
login_manager.init_app(app)
login_manager.login_view = 'auth.login'

# Add unauthorized handler to prevent redirects for API routes
@login_manager.unauthorized_handler
def unauthorized():
    # Check if the request is for an API endpoint
    if request.path.startswith('/api/'):
        return jsonify({"error": "Unauthorized"}), 401
    # For non-API routes, let Flask-Login handle redirect normally
    return login_manager.unauthorized()

# Register auth blueprint
app.register_blueprint(auth_bp)

# Create tables and seed admin user
with app.app_context():
    db.create_all()
    
    # Create default admin user if not exists
    admin = User.query.filter_by(username='happyadmin').first()
    if not admin:
        admin = User(username='happyadmin', role='admin')
        admin.set_password('Smiles@123')
        db.session.add(admin)
        db.session.commit()
        print("✅ Created admin user: happyadmin / Smiles@123")
    else:
        print("ℹ️ Admin user already exists")

# Mock dashboard endpoint for frontend
@app.route('/dashboard')
def dashboard():
    return jsonify({
        'total_resumes': 0,
        'total_jds': 0,
        'pending': 0
    })

# Mock employees endpoint for frontend
@app.route('/api/employees')
def employees():
    return jsonify([])

@app.route('/health')
def health():
    return jsonify({"status": "healthy"})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5050, debug=True)
