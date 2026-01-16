from flask import Flask
from flask_migrate import Migrate
from extensions import db
from models import *  # import all models (jd, candidate, etc.)

app = Flask(__name__)
app.config.from_object('config')  # or your config

db.init_app(app)
migrate = Migrate(app, db)

@app.cli.command()
def test():
    print("Migrations ready!")
