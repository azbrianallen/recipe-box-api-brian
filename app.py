import os
from importlib import import_module

try:
    load_dotenv = import_module("dotenv").load_dotenv
except ModuleNotFoundError:
    load_dotenv = None

if load_dotenv is not None:
    load_dotenv()

print("DATABASE_PATH from env:", repr(os.getenv("DATABASE_PATH")))

from app import create_app

app = create_app()

if __name__ == "__main__":
    app.run(debug=True)