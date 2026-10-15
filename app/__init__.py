from app.db import get_db
import os
import sqlite3
from datetime import datetime, timedelta, timezone
from functools import wraps

import jwt  # type: ignore[reportMissingImports]
from flask import Flask, current_app, g, jsonify, request
from jwt import ExpiredSignatureError, InvalidTokenError  # type: ignore[reportMissingImports]
from werkzeug.security import check_password_hash, generate_password_hash
from app.routes.auth import auth_bp 
from app.routes.recipes import recipes_bp


DATABASE = os.environ.get("DATABASE_PATH")
if not DATABASE:
    raise RuntimeError("DATABASE_PATH environment variable is required")

def recipe_to_dict(row):
    if row is None:
        return None
    return {key: row[key] for key in row.keys()}

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


class BaseConfig(Config):
    JWT_SECRET_KEY = os.environ.get("JWT_SECRET_KEY")
    if not JWT_SECRET_KEY:
        raise RuntimeError("JWT_SECRET_KEY environment variable is required")

class DevConfig(BaseConfig):
    # later we can add more dev-specific settings here
    pass

class ProdConfig(BaseConfig):
    # later we can add more prod-specific settings here
    pass

config_classes = {
    "development": DevConfig,
    "production": ProdConfig,
}

def create_app(config_name="development"):
    app = Flask(__name__)

    config_class = config_classes.get(config_name, DevConfig)
    app.config.from_object(config_class)
    print("JWT_SECRET_KEY value:", repr(app.config["JWT_SECRET_KEY"]))
    app.register_blueprint(auth_bp)
    app.register_blueprint(recipes_bp, url_prefix="/recipes") 

    @app.teardown_appcontext
    def close_db(exception):
        db = g.pop("db", None)
        if db is not None:
            db.close()

    return app
