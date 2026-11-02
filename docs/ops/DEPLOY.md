# Deploy in 15 minutes (external-product v0)

## Local single owner (unchanged default)
```sh
pip install -e ".[test]"
bash scripts/run_dev.sh          # 127.0.0.1:8765, no accounts
```

## Multi-tenant instance
```sh
docker compose up -d --build
curl -s localhost:8765/health
curl -s -X POST localhost:8765/auth/signup \
  -H 'Content-Type: application/json' \
  -d '{"email":"owner@example.com","password":"change-me-8"}'
```
The first account is the tenant owner; `POST /auth/invite` adds members (owner only).
Only owners may approve or run missions in that tenant.

## Upgrade
```sh
docker compose build && docker compose up -d
```
Schema migrations run on startup (`db._migrate_tenancy`, `auth._init_schema`) and are
forward-only; take a copy of the volume before upgrading:
`docker run --rm -v nexara-data:/d -v $PWD:/out alpine tar czf /out/backup.tgz -C /d .`

## Rollback
```sh
docker compose down
docker run --rm -v nexara-data:/d -v $PWD:/in alpine sh -c 'rm -rf /d/* && tar xzf /in/backup.tgz -C /d'
docker compose up -d --build
```

## What this image does NOT give you yet
- TLS termination (put it behind a reverse proxy),
- rate limiting, email verification, password reset,
- Linux container sandbox is used for tool execution; macOS uses sandbox-exec.
