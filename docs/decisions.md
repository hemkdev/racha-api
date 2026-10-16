# Design decisions

What was chosen, what was rejected and why. Database details (constraints, `PROTECT`, the stored
price) are in [database.md](database.md).

## 1. Custom user model from the first migration

Swapping Django's user model after migrations exist is painful; starting with `AbstractUser` costs
nothing. `role` and `phone` were added later without touching `AUTH_USER_MODEL`.

## 2. The booking is the order item

There is no `OrderItem`. An item table carries a quantity, and here there is none: three hours are
three bookings. An `OrderItem` would only hold the price, which fits on the booking. As a bonus,
one order can mix courts and days.

## 3. Fixed one-hour slots instead of free time ranges

Every booking starts on the hour and lasts one hour. With free ranges, preventing overlap needs an
exclusion constraint, free slots become gap calculations, peak prices must be prorated and partial
cancellation splits a range. With slots, a unique index on `(court, starts_at)` is enough, as long
as two check constraints keep every slot on the hour and one hour long. If 90-minute games are ever
needed, the answer is 30-minute slots.

## 4. Maintenance is a kind of booking

The first design had a separate `Blackout` table for maintenance. Stored as one-hour slots, it has the same shape
as a booking, so it became `kind = MAINTENANCE`. One table means one unique index prevents every
conflict, customer or maintenance. A check constraint stops the optional fields from mixing: a
customer booking has an order and a price, maintenance has a reason and neither.

## 5. A purchase is all or nothing, and says what failed

Booking two of three hours without saying so is worse than booking nothing. Every slot is
validated before anything is written, and the response lists all the failures. If another purchase
takes a slot between the check and the insert, the unique index refuses it and the whole
transaction rolls back.

## 6. A court has a list of sports

A sand court hosts beach tennis, beach volleyball and footvolley, so `sports` is a PostgreSQL array
checked by the database. A `Sport` table with a many-to-many relation only pays off if the list
changes without a deploy, and here it is a business rule.

## 7. One Django app

Everything lives in `core`. Several apps would add cross-app migrations and string foreign keys
for four models in one domain. It will split when that hurts.

## 8. Design the whole schema first, build one entity at a time

The full ER diagram came first, on paper. Then each entity went end to end (model, migration,
admin, serializer, view, URL, test) before the next, because a model is only proven by a working
endpoint.

## 9. PostgreSQL everywhere, including locally

Local, CI and production run the same major version. SQLite accepts what PostgreSQL refuses, and
the schema needs PostgreSQL: arrays and `DATE_TRUNC` do not exist in SQLite. The production
database is never used for development.

## 10. The application on a VM, the database elsewhere

The API runs on an Oracle Cloud Always Free ARM VM, which does not sleep like free platform tiers.
The database is on Neon, so losing the VM means downtime, not data loss. The VM has no open ports:
traffic and deploys go through a Cloudflare Tunnel.

## 11. Payment at the front desk, and a cap on unpaid hours

Orders stay `PENDING` until staff mark them `PAID`, often after the game. To stop a customer from
holding the schedule without paying, they can hold at most 4 future hours in pending orders. The
check runs in the purchase transaction with the customer's row locked, so two simultaneous
purchases cannot both pass. Staff buying for a customer are exempt.

## 12. No retries inside the application

When Neon fails, a request fails with it: no retry loop around queries. Retrying inside a request
multiplies the load exactly when the database is struggling, holds a gunicorn worker for longer,
and the client can repeat the call itself. `CONN_HEALTH_CHECKS` already drops dead connections
before a request uses them. The one bounded retry is in the deploy: the smoke check polls
`/health/` up to ten times, since a fresh container takes a few seconds to answer.
