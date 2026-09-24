"""Recipe Box API — BE104 course skeleton.

A working Flask + SQLite CRUD API for recipes with JWT authentication.
"""
import os
import sqlite3
from datetime import datetime, timedelta, timezone
from functools import wraps

import jwt  # type: ignore[reportMissingImports]
from flask import Flask, g, jsonify, request
from jwt import ExpiredSignatureError, InvalidTokenError  # type: ignore[reportMissingImports]
from werkzeug.security import check_password_hash, generate_password_hash
DATABASE = "recipes.db"

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

app = Flask(__name__) 

app.config["JWT_SECRET_KEY"] = os.environ.get("JWT_SECRET_KEY")
print("JWT_SECRET_KEY loaded?", bool(app.config["JWT_SECRET_KEY"]))


# ==========================================
# Database Helpers
# ==========================================

def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DATABASE)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


@app.teardown_appcontext
def close_db(exception):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def recipe_to_dict(row):
    return {
        "id": row["id"],
        "title": row["title"],
        "ingredients": row["ingredients"],
        "instructions": row["instructions"],
        "is_public": bool(row["is_public"]),
    }


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

        try:
            claims = jwt.decode(
                token,
                app.config["JWT_SECRET_KEY"],
                algorithms=["HS256"],
            )
            g.user_id = claims.get("sub")
            g.user_role = claims.get("role")  # new line
        except ExpiredSignatureError:
            return jsonify({"error": "token has expired, please log in again"}), 401
        except InvalidTokenError:
            return jsonify({"error": "invalid credentials"}), 401

        return f(*args, **kwargs)

    return decorated


# ==========================================
# Auth Routes
# ==========================================

@app.post("/register")
def register():
    data = request.get_json(silent=True)

    if (
        not data
        or not data.get("email")
        or not data.get("name")
        or not data.get("password")
    ):
        return jsonify({"error": "email, name, and password are required"}), 400

    email = data["email"]
    name = data["name"]
    raw_password = data["password"]

    # Hash using werkzeug.security consistently
    password_hash = generate_password_hash(raw_password)

    db = get_db()
    try:
        cur = db.execute(
            "INSERT INTO users (email, name, password_hash) VALUES (?, ?, ?)",
            (email, name, password_hash),
        )
        db.commit()
    except sqlite3.IntegrityError:
        return jsonify({"error": "a user with that email already exists"}), 409

    row = db.execute(
        "SELECT id, email, name FROM users WHERE id = ?", (cur.lastrowid,)
    ).fetchone()

    return jsonify(
        {
            "id": row["id"],
            "email": row["email"],
            "name": row["name"],
        }
    ), 201


@app.post("/login")
def login():
    data = request.get_json(silent=True)

    if not data:
        return jsonify({"error": "email and password are required"}), 400

    email = data.get("email")
    password = data.get("password")

    if not email or not password:
        return jsonify({"error": "email and password are required"}), 400

    db = get_db()
    row = db.execute(
        "SELECT id, email, name, password_hash, role FROM users WHERE email = ?",
        (email,),
    ).fetchone()

    if row is None or not check_password_hash(row["password_hash"], password):
        return jsonify({"error": "invalid credentials"}), 401

    payload = {
        "sub": row["id"],
        "email": row["email"],
        "name": row["name"],
        "role": row["role"],  # ✅ new
        "exp": datetime.now(timezone.utc) + timedelta(minutes=60),
    }

    token = jwt.encode(
        payload,
        app.config["JWT_SECRET_KEY"],
        algorithm="HS256",
    )

    return jsonify({"token": token}), 200

# ==========================================
# Recipe Routes
# ==========================================

@app.get("/")
def hello():
    return jsonify({"message": "Recipe Box API", "recipes": "/recipes"})


@app.get("/recipes")
def list_recipes():
    rows = get_db().execute("SELECT * FROM recipes ORDER BY id").fetchall()
    return jsonify([recipe_to_dict(r) for r in rows])


@app.get("/recipes/<int:recipe_id>")
def get_recipe(recipe_id):
    row = get_db().execute(
        "SELECT * FROM recipes WHERE id = ?", (recipe_id,)
    ).fetchone()
    if row is None:
        return jsonify({"error": "recipe not found"}), 404
    return jsonify(recipe_to_dict(row))


@app.post("/recipes")
@token_required
def create_recipe():
    user_id = g.user_id

    data = request.get_json(silent=True)
    if not data or not data.get("title") or not data.get("ingredients"):
        return jsonify({"error": "title and ingredients are required"}), 400

    db = get_db()
    try:
        cur = db.execute(
            "INSERT INTO recipes (title, ingredients, instructions, is_public, owner_id)"
            " VALUES (?, ?, ?, ?, ?)",
            (
                data["title"],
                data["ingredients"],
                data.get("instructions", ""),
                1 if data.get("is_public", True) else 0,
                user_id,
            ),
        )
        db.commit()
    except sqlite3.IntegrityError:
        return jsonify({"error": "a recipe with that title already exists"}), 409

    row = db.execute(
        "SELECT * FROM recipes WHERE id = ?", (cur.lastrowid,)
    ).fetchone()
    return jsonify(recipe_to_dict(row)), 201


@app.patch("/recipes/<int:recipe_id>")
@token_required
@owner_or_admin_required
def update_recipe(recipe_id):
    db = get_db()

    data = request.get_json(silent=True) or {}
    fields, values = [], []
    for column in ("title", "ingredients", "instructions"):
        if column in data:
            fields.append(f"{column} = ?")
            values.append(data[column])
    if "is_public" in data:
        fields.append("is_public = ?")
        values.append(1 if data["is_public"] else 0)

    if not fields:
        return jsonify({"error": "nothing to update"}), 400

    values.append(recipe_id)
    try:
        cur = db.execute(
            f"UPDATE recipes SET {', '.join(fields)} WHERE id = ?", values
        )
        db.commit()
    except sqlite3.IntegrityError:
        return jsonify({"error": "a recipe with that title already exists"}), 409

    if cur.rowcount == 0:
        return jsonify({"error": "recipe not found"}), 404

    row = db.execute(
        "SELECT * FROM recipes WHERE id = ?", (recipe_id,)
    ).fetchone()
    return jsonify(recipe_to_dict(row))


@app.delete("/recipes/<int:recipe_id>")
@token_required
@owner_or_admin_required
def delete_recipe(recipe_id):
    db = get_db()
    db.execute("DELETE FROM recipes WHERE id = ?", (recipe_id,))
    db.commit()
    return "", 204


if __name__ == "__main__":
    app.run(debug=True)