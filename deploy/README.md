# Serving deployment — cfdb.marc4data.com

DigitalOcean droplet (SFO, 1 GiB / 1 vCPU, $6/mo) running three services under Compose:
serving Postgres, the Streamlit site, and a Cloudflare Tunnel connector.

## The security posture, and why it looks like this

**No inbound ports.** The firewall allows SSH and nothing else; the tunnel dials *out* to
Cloudflare, so the site is reachable without opening anything. Postgres is not published to
the host at all — it exists only on the Docker network, where the site reaches it by
service name. Cloudflare Access is the auth boundary; there is no auth code in the app.

**Two database roles.** The owner runs migrations and receives publishes; the site connects
as `cfdb_read`, which holds SELECT and nothing else. Serving is read-only by architecture.

Secrets live in `/opt/cfdb/.env` (0600), generated on the box so they never transit a
laptop or a git history.

## Layout

| Path | What |
|---|---|
| `/opt/cfdb/docker-compose.yml` | the stack |
| `/opt/cfdb/.env` | generated secrets, 0600 |
| `/opt/cfdb/site/` | Streamlit app + Dockerfile |
| `/opt/cfdb/backups/` | nightly dumps, 14-day retention |
| `/etc/cron.d/cfdb-backup` | 09:15 UTC nightly |

## Operating it

```bash
ssh root@143.110.225.139
cd /opt/cfdb
docker compose ps
docker compose logs -f site
docker compose --profile tunnel up -d      # once the tunnel token is set
./backup.sh                                # on demand; cron runs it nightly
```

Redeploy after changing site code or the stack:

```bash
# from the repo root
rsync -az deploy/docker-compose.yml deploy/backup.sh root@143.110.225.139:/opt/cfdb/
rsync -az --delete --exclude '__pycache__' \
  deploy/site/Dockerfile deploy/site/requirements.txt \
  site/app.py site/lib site/pages \
  root@143.110.225.139:/opt/cfdb/site/
ssh root@143.110.225.139 'cd /opt/cfdb && docker compose build site && docker compose up -d site'
```

**One rsync, and the source directories have no trailing slash.** Both details are load
bearing, and both were got wrong on a real deploy:

- `site/lib/` with a trailing slash copies the directory's *contents* into the destination
  root, so every module lands beside `app.py` and the `lib` package does not exist. Without
  the slash the directory itself is copied, which is what the Dockerfile's `COPY lib/` needs.
- Two `--delete` invocations against the same destination fight each other. The second one
  deleted the `Dockerfile` the first had just placed, and the build then failed with
  `failed to read dockerfile`. `--delete` is still right — a page module removed from the
  repo but left on the box keeps being served — it just has to be one command that knows
  about everything.

The list also has to include `lib/` and `pages/` at all: it once read `app.py` and `db.py`
alone, which produces a container that builds cleanly, starts cleanly, and raises
`ModuleNotFoundError: No module named 'lib'` the moment anyone loads a page.

Verify after deploying, because "the container is up" is not "the site works":

```bash
ssh root@143.110.225.139 'cd /opt/cfdb && docker compose logs --tail=30 site'
curl -sS -o /dev/null -w '%{http_code}\n' https://cfdb.marc4data.com   # 302 -> Access
```

A 302 is the expected answer: Cloudflare Access is redirecting to its login. A 200 from an
unauthenticated request would mean the Access policy is missing.

## Publishing marts

```bash
python -m src.publish_marts            # transform Postgres -> serving Postgres
python -m src.publish_marts --dry-run
```

Publishing goes over SSH rather than a database connection, because the droplet publishes
no ports — `pg_dump` locally, streamed over SSH, restored inside the container. It is
idempotent (`--clean --if-exists`), re-grants SELECT to the read-only role afterwards
(a recreated table does not inherit the old one's grants), and verifies row counts on both
sides rather than assuming the restore worked.

## Backups

Nightly `pg_dump` at 09:15 UTC, gzipped, 14 days retained. The script **fails loudly on a
suspiciously small dump** rather than rotating good backups out in favour of an empty one —
which is exactly what it did on first run against an empty database.

The serving database is derived data: a full rebuild is a publish away, so these dumps are
convenience rather than the last line of defence. Restoring is minutes; rebuilding is a
pipeline cycle.

## Remaining manual steps (Cloudflare)

The tunnel and Access policy are created in the Cloudflare dashboard, then the token goes
in `/opt/cfdb/.env`:

1. **Zero Trust → Networks → Tunnels → Create a tunnel** (Cloudflared), name it `cfdb`.
2. Copy the token into `/opt/cfdb/.env` as `CLOUDFLARE_TUNNEL_TOKEN=...`
3. Add a **public hostname**: `cfdb.marc4data.com` → `http://site:8501`
   (service name, not localhost — the connector shares the Docker network).
4. **Zero Trust → Access → Applications → Add a self-hosted application** for
   `cfdb.marc4data.com`, policy = allow the specific email addresses.
5. On the droplet: `cd /opt/cfdb && docker compose --profile tunnel up -d`

Step 4 is what keeps strangers out. Until it exists, the hostname from step 3 would be
publicly reachable, so add the Access application before advertising the URL.
