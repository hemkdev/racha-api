# racha-api

REST API for booking sports courts with Django, DRF and PostgreSQL. **Work in progress.**

A study project on the ORM and data modeling: business rules live in database constraints,
and each rule is tested at both the database and the API level. CI (lint, tests, Docker build)
is required to merge into `main`.

**Stack:** Python 3.14 · Django 5.2 · DRF · PostgreSQL 17 · pytest · uv · Docker · GitHub Actions

## Running locally

```bash
docker compose up -d db
cp .env.example .env   # set SECRET_KEY and DATABASE_URL=postgresql://racha:racha@localhost:5432/racha
uv sync
uv run manage.py migrate
uv run manage.py runserver   # http://localhost:8000/api/v1/
uv run pytest
```

## Next steps

Known gaps, each one the next thing to build:

- [ ] **Orders** — atomic purchase of multiple slots
- [ ] **Deployment** — Oracle Cloud ARM VM + Neon PostgreSQL

## License

MIT
