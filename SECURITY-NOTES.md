\## 2026-09-12 – Anonymous access baseline



\- GET /recipes – 200 OK, returns all recipes including non-public (`is\_public: false`) entries like "Secret family hot sauce".

\- GET /recipes/3 – 200 OK, returns full details of the non-public recipe with id 3.

\- PATCH /recipes/3 – 200 OK, allows anonymous change of the recipe title (e.g., to "Leaked family hot sauce").

\- DELETE /recipes/3 – 204 No Content, allows anonymous deletion; subsequent GET /recipes/3 returns 404 "recipe not found".

