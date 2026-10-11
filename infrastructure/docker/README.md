# infrastructure/docker/

The canonical local-dev stack is the `docker-compose.yml` at the repo
root (validated with `docker compose config` — see
`docs/deployment.md`), not a file in this folder — keeping one compose
file rather than splitting dev/prod ones early avoids the two drifting
apart while this project is still young.

This folder is where a production-specific compose override would live
once there's an actual target to write one for — e.g.
`docker-compose.prod.yml` swapping the `nginx` service's image for one
that TLS-terminates, pointing `DATABASE_URL` at a managed Postgres
instead of the `db` service, and dropping the `ports:` host-binding on
`db` entirely (it's only exposed at 5432 in the root compose file for
local psql access during development). None of that has a concrete
target environment yet, so nothing here is a guess dressed up as a
config file — see `docs/deployment.md`'s "Environment constraints
encountered" section for the honesty pattern this follows.

`backend/Dockerfile` (non-root user, healthcheck) is the actual
production-target image definition and lives with the code it builds,
not here.
