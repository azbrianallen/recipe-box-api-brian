"""Recipe Box API — BE104 course skeleton.

A working Flask + SQLite CRUD API for recipes. It stores data perfectly —
and it trusts everyone. There is no authentication and no authorization yet.
That is the point: you will add both, lesson by lesson, in Units 2 and 3.
"""

import sqlite3
from security_utils import create_password_hash, verify_password
from werkzeug.security import generate_password_hash, check_password_hash
from flask import Flask, g, jsonify, request

import os
from dotenv import load_dotenv
import jwt
from datetime import datetime, timedelta

load_dotenv()

DATABASE = "recipes.db"

app = Flask(__name__)

app.config["JWT_SECRET"] = os.environ.get("JWT_SECRET")
print("JWT_SECRET loaded?", bool(app.config["JWT_SECRET"]))

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
def create_recipe():
    data = request.get_json(silent=True)
    if not data or not data.get("title") or not data.get("ingredients"):
        return jsonify({"error": "title and ingredients are required"}), 400
    db = get_db()
    try:
        cur = db.execute(
            "INSERT INTO recipes (title, ingredients, instructions, is_public)"
            " VALUES (?, ?, ?, ?)",
            (
                data["title"],
                data["ingredients"],
                data.get("instructions", ""),
                1 if data.get("is_public", True) else 0,
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
def update_recipe(recipe_id):
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "a JSON body is required"}), 400
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
    db = get_db()
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
def delete_recipe(recipe_id):
    db = get_db()
    cur = db.execute("DELETE FROM recipes WHERE id = ?", (recipe_id,))
    db.commit()
    if cur.rowcount == 0:
        return jsonify({"error": "recipe not found"}), 404
    return "", 204

@app.post("/register")
def register():
    data = request.get_json(silent=True)

    # Validation
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

    # Hash the password – never store or return raw_password
    password_hash = create_password_hash(raw_password)

    db = get_db()
    try:
        cur = db.execute(
            "INSERT INTO users (email, name, password_hash) VALUES (?, ?, ?)",
            (email, name, password_hash),
        )
        db.commit()
    except sqlite3.IntegrityError:
        # email is UNIQUE, so this means duplicate account
        return jsonify({"error": "a user with that email already exists"}), 409

    # Fetch the newly created user (without password fields)
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
        "SELECT id, email, name, password_hash FROM users WHERE email = ?",
        (email,),
    ).fetchone()

    # Generic failure: unknown email OR wrong password
    if row is None or not check_password_hash(row["password_hash"], password):
        return jsonify({"error": "invalid credentials"}), 401

    # Success: issue a signed JWT carrying identity + expiry
    payload = {
        "sub": row["id"],                 # subject = user id
        "email": row["email"],
        "name": row["name"],
        "exp": datetime.utcnow() + timedelta(hours=1),
    }

    token = jwt.encode(
        payload,
        app.config["JWT_SECRET"],
        algorithm="HS256",
    )

    return jsonify(
        {
            "token": token,
        }
    ), 200

if __name__ == "__main__":
    app.run(debug=True)
