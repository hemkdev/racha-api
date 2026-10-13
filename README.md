# racha-api

REST API for booking sports courts with Django, DRF and PostgreSQL. **Work in progress.**

A study project on the ORM and data modeling: business rules live in database constraints,
and each rule is tested at both the database and the API level. CI (lint, tests, Docker build)
is required to merge into `main`.

**Stack:** Python 3.14 · Django 5.2 · DRF · PostgreSQL 17 · pytest · uv · Docker · GitHub Actions

## How it works

Courts are rented by the hour, from 8:00 to 22:00, with peak hours (18:00 to 22:00) charged
at 1.5×. Anyone can see the courts and a day's slots at `GET /api/v1/courts/{id}/slots/?date=YYYY-MM-DD`;
everything else needs a JWT from `POST /api/v1/token/`.

A customer buys one or more slots at once with `POST /api/v1/orders/`: either every slot is
booked or none is. Payment happens at the front desk, with no deadline: the order stays
`PENDING` until staff confirm it (`/confirm/`), which marks it `PAID`. While pending, the
customer can cancel the whole order or single bookings; cancelling the last active booking
cancels the order. To keep slots from being held indefinitely, a customer can hold at most
4 future hours in pending orders; staff buying on a customer's behalf are exempt. Staff also
block slots for maintenance through `POST /api/v1/bookings/`.

There is no sign-up: customers are created by staff in the Django admin. `createsuperuser`
creates a `STAFF` user. Tokens use simplejwt's defaults (5-minute access, 1-day refresh) and
there is no server-side logout; a token stays valid until it expires.

The API is throttled per client: 60 requests per minute for anonymous clients, 300 for
authenticated users, and 5 per minute on `/api/v1/token/`.

Most rules are database constraints. A few depend on the clock or on another row and are
enforced only by the API: working hours, refusing past slots, repeated sports on a court,
and an order belonging to a `CUSTOMER`.

## Running locally

```bash
docker compose up -d db
cp .env.example .env   # set SECRET_KEY and DATABASE_URL=postgresql://racha:racha@localhost:5432/racha
uv sync
uv run manage.py migrate
uv run manage.py createsuperuser
uv run manage.py runserver   # http://localhost:8000/api/v1/
uv run pytest
```

## Next steps

Known gaps, each one the next thing to build:

- [ ] **Deployment** — Oracle Cloud ARM VM + Neon PostgreSQL, behind a Cloudflare Tunnel

## License

MIT
