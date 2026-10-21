# Refactor Plan for Recipe Box

## 1. Current Responsibilities in app.py

- Startup / app wiring
- HTTP routes (auth + recipes)
- Auth mechanics (hashing passwords, JWT encode/decode, decorators)
- Database / persistence (SQLite connection + queries)
- Config / secrets (env, JWT_SECRET_KEY, etc.)
- Error handling / responses

Total responsibility count in `app.py`: 6

---

## 2. Target Layout (no behavior changes)

```text
recipe-box/
  app.py                  # entrypoint to run the server

  auth/
    routes.py             # /register, /login, maybe /users
    service.py            # auth logic: hashing, JWT encode/decode, role checks
    data.py               # user DB queries

  recipes/
    routes.py             # /recipes endpoints
    service.py            # recipe business rules (ownership/admin checks)
    data.py               # recipe DB queries

  common/
    db.py                 # DB connection helpers
    errors.py             # shared error / response helpers 

## 3. Acceptance List (Current API Behavior) 

1. GET - / → Inputs: None | Expected Status: 200 OK | Important Rules: Returns a welcome JSON object with a link to /recipes.

2. POST - /register → Inputs: email, name, password (JSON) | Expected Status: 201 Created | Important Rules: Validates presence of all 3 fields (returns 400 if missing); hashes password; handles email conflicts (returns 409 if email already exists); returns id, email, and name without password hash.

3. POST - /login → Inputs: email, password (JSON) | Expected Status: 200 OK | Important Rules: Validates presence of inputs (returns 400 if empty); checks password hash against DB; returns a signed JWT token valid for 60 minutes containing user id (as sub), email, name, and role. Returns 401 on bad credentials.

4. GET - /recipes → Inputs: None | Expected Status: 200 OK | Important Rules: Returns a JSON list containing all recipes in the system sorted by ID.

5. GET - /recipes/<int:recipe_id> → Inputs: recipe_id (URL path) | Expected Status: 200 OK | Important Rules: Returns a single recipe JSON object if it exists; returns 404 Not Found with an error message if the ID doesn't exist.

6. POST - /recipes → Inputs: Authorization: Bearer <token> (Header), title, ingredients, instructions (optional), is_public (optional JSON) | Expected Status: 201 Created | Important Rules: Requires a valid, unexpired token (returns 401 if missing/invalid/expired). Requires title and ingredients (returns 400 if missing). Sets default is_public to true if omitted. Assigns recipe ownership to the authenticated user's ID. Returns 409 if a recipe title already exists.

7. PATCH - /recipes/<int:recipe_id> → Inputs: Authorization: Bearer <token> (Header), recipe_id (URL path), any combination of title, ingredients, instructions, is_public (JSON) | Expected Status: 200 OK | Important Rules: Requires valid auth token (401). Requires user to be either the recipe's owner or an admin (returns 403 if forbidden, 404 if recipe doesn't exist). Requires at least one field to update (returns 400 if empty body). Enforces database uniqueness on title (returns 409 if name clashes). Returns the fully updated recipe payload.

8. DELETE - /recipes/<int:recipe_id> → Inputs: Authorization: Bearer <token> (Header), recipe_id (URL path) | Expected Status: 204 No Content | Important Rules: Requires valid auth token (401). Requires user to be the owner or an admin (returns 403 if unauthorized, 404 if recipe doesn't exist). Successfully removes the item from the database and returns an empty body.

Total acceptance-list items: 8

--- 

## 3. Endpoints that must NEVER be cached

1. GET /me — user-specific and authorization-sensitive data; caching could leak one user’s data to another.

2. POST /login — response depends on credentials and current session state; must always be fresh. 
