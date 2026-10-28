from app.db import get_db
from app.extensions import db, migrate, cache, limiter
import os
import sqlite3
from datetime import datetime, timedelta, timezone
from functools import wraps

import jwt  # type: ignore[reportMissingImports]
from flask import Flask, app, current_app, g, jsonify, request
from jwt import ExpiredSignatureError, InvalidTokenError  # type: ignore[reportMissingImports]
from werkzeug.security import check_password_hash, generate_password_hash
from app.routes.auth import auth_bp 
from app.routes.recipes import recipes_bp
from app.routes.favorites import favorites_bp 

from importlib import import_module

try:
    load_dotenv = import_module("dotenv").load_dotenv
except ModuleNotFoundError:
    load_dotenv = None

if load_dotenv is not None:
    load_dotenv()

# ==========================================
# Authentication Decorator
# ==========================================

def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            return jsonify({"error": "invalid credentials"}), 401

        token = auth_header.split(" ", 1)[1].strip()
        print("DEBUG TOKEN FROM HEADER:", repr(token))

        try:
            claims = jwt.decode(
                token,
                current_app.config["JWT_SECRET_KEY"],
                algorithms=["HS256"],
            )
            print("DEBUG CLAIMS:", claims)
            g.user_id = int(claims.get("sub"))
            g.user_role = claims.get("role")
        except ExpiredSignatureError:
            print("DEBUG: ExpiredSignatureError")
            return jsonify({"error": "token has expired, please log in again"}), 401
        except InvalidTokenError as e:
            print("DEBUG: InvalidTokenError", repr(str(e)))
            return jsonify({"error": "invalid credentials"}), 401

        return f(*args, **kwargs)

    return decorated

# ==========================================
# Owner or Admin Required 
# ==========================================

def owner_or_admin_required(f):
    @wraps(f)
    def wrapper(recipe_id, *args, **kwargs):
        db = get_db()
        recipe = db.execute(
            "SELECT owner_id FROM recipes WHERE id = ?",
            (recipe_id,),
        ).fetchone()

        if recipe is None:
            return jsonify({"error": "recipe not found"}), 404

        user_id = g.user_id
        user_role = g.user_role

        if recipe["owner_id"] != user_id and user_role != "admin":
            return jsonify({"error": "forbidden"}), 403

        # Optionally stash recipe in g so route doesn’t re-query
        g.recipe = recipe

        # Call the original view
        return f(recipe_id, *args, **kwargs)

    return wrapper

class Config:
    pass

import os

class BaseConfig(Config):
    JWT_SECRET_KEY = os.environ.get("JWT_SECRET_KEY")
    DATABASE_PATH = os.environ.get("DATABASE_PATH")
    NUTRITION_SERVICE_BASE_URL = os.environ.get("NUTRITION_SERVICE_BASE_URL", "http://127.0.0.1:5001")

    BASE_DIR = os.path.abspath(os.path.dirname(__file__))  # app/ directory

    # For now, just use DATABASE_PATH directly; let env control the full path
    SQLALCHEMY_DATABASE_URI = f"sqlite:///{DATABASE_PATH}"

    SQLALCHEMY_TRACK_MODIFICATIONS = False

    CACHE_TYPE = "SimpleCache"
    CACHE_DEFAULT_TIMEOUT = 60  # seconds for now

class DevConfig(BaseConfig):
    # later we can add more dev-specific settings here
    pass

class ProdConfig(BaseConfig):
    # later we can add more prod-specific settings here
    pass

class TestConfig(BaseConfig):
    DATABASE_PATH = "instance/test_recipes.db"


config_classes = {
    "development": DevConfig,
    "production": ProdConfig,
    "testing": TestConfig,
}

def create_app(config_name="development"):
    app = Flask(__name__)

    config_class = config_classes.get(config_name, DevConfig)
    app.config.from_object(config_class)
    
    db.init_app(app)
    migrate.init_app(app, db)
    cache.init_app(app)
    limiter.init_app(app)
    
    print("JWT_SECRET_KEY value:", repr(app.config["JWT_SECRET_KEY"]))
    app.register_blueprint(auth_bp, url_prefix="/auth")
    app.register_blueprint(recipes_bp, url_prefix="/recipes") 
    app.register_blueprint(favorites_bp, url_prefix="/favorites")
    
    @app.teardown_appcontext
    def close_db(exception):
        db = g.pop("db", None)
        if db is not None:
            db.close()

    return app
