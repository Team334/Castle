# Automatic fuel estimates

Only newly saved scouting records with every fuel count left blank are eligible.
Entering any fuel count, including zero or ferried fuel, keeps the entire record
manual. Touching a fuel counter and then clearing it also keeps the record manual.
Existing records are never enrolled. Saving an edit stops automatic updates for
that record, including when the edit deliberately sets counts to zero.

## How the estimate works

Match13 provides ratings, not measured individual fuel counts. Castle combines
the latest event-specific ratings from `GET /v1/events/{eventKey}/teams` with
official alliance fuel counts from TBA's event matches endpoint. For each phase,
Castle allocates the alliance count proportionally across its three teams:

`team estimate = alliance phase count × team rating / sum of alliance ratings`

Autonomous uses `xAuto`. Transition, teleop shifts, and endgame fuel use `xTele`.
The `xEnd` tower rating is not a fuel count. Negative weights are clamped to zero,
and disqualified teams receive zero weight. Largest-remainder rounding preserves
the official count when the three estimated contributions are added together.
Missing ratings, missing breakdowns, or unplayed matches remain pending.

This is Castle's approximate allocation, not a Match13 measurement of that robot
in that match. It cannot identify unusual individual performance or when a robot
shot within teleop. As event ratings improve, eligible records are recalculated.
Manual scouting records are never adjusted to make totals agree with this model.
Ferried fuel cannot be inferred; Scout displays it as unknown for estimated
records. Estimated records are labeled in Scout and Match View, and CSV exports
include a Fuel Source column. Aggregate fuel statistics use the stored estimates.
The phase mapping currently supports the 2026 game only.

## Requests and limits

The [Match13 API documentation](https://www.match13.com/docs/api#description/rate-limit)
documents account-wide limits of 60 requests/minute, 1,000/hour, and 30,000/week.
All keys on an account share those limits; errors and HTTP 304 responses count.

Castle uses one bulk ratings request per event, rather than per robot, match, or
browser. A SQLite cache and scheduler are shared across workers on the same host.
Active events are checked about every five minutes: typically **12 Match13
requests/hour/event**, regardless of how many users are scouting. A corresponding
TBA event-matches request supplies official results. Events whose entire official
schedule finished over 48 hours ago are checked at most daily. Events without
active eligible records make no provider requests.

Castle reserves a request before sending it and imposes conservative rolling
limits of **30/minute, 600/hour, and 15,000/week**. It respects remaining/reset
headers and `Retry-After`, sends `If-None-Match` when an ETag is available, and
keeps cached data during failures. Temporary failures wait 15 minutes; rejected
credentials wait one hour. These local budgets cannot reserve capacity against
other applications using the same account; provider response headers handle that
case. All network work happens in a background thread. Browser refreshes only
read Castle's saved values and never call Match13.

## VPS configuration and persistence

Add `MATCH_13_API_KEY` to the VPS environment or `.env`, alongside the existing
`TBA_AUTH_KEY`. `MATCH13_API_KEY` is accepted as an alias. Restart Castle after
changing keys. No additional Python dependency or MongoDB migration is required.
The existing Gunicorn service can continue using its current worker configuration.

By default, eligibility, manual overrides, cache, and request budgets are stored
in `instance/match13.sqlite` under Castle's application root. The directory is
ignored by Git. **Preserve this state directory when deploying or restoring** so
estimate labels and future updates survive. Losing it does not enroll old records
or overwrite manual counts, but previously enrolled records stop refreshing.

Optionally set `MATCH13_STATE_PATH` to a persistent absolute SQLite file path,
such as `/var/lib/castle/match13.sqlite`. Every worker on this host must use the
same path, and the service user must be able to write its directory. To back it
up, stop Castle briefly and copy the state directory, or use SQLite's online
backup API. Copying only a live database file can omit WAL transactions. Multiple
hosts sharing one API account require coordinated budgets beyond this single-host
scheduler.

MongoDB retains its current document format, collections, and indexes. The
background writer only updates the seven existing scored-fuel fields on enrolled
records, guarded by their identity and every previous fuel value. Eligibility and
provenance are stored outside MongoDB; no historical-data scan or backfill runs.
