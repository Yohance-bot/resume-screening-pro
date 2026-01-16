from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_migrate import Migrate

# Shared database instance
db = SQLAlchemy()

# Shared migration instance  
migrate = Migrate()

# Shared login manager instance
login_manager = LoginManager()
