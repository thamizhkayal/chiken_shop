# Deployment guide

## Production prerequisites

- A Linux host or VM with Docker Engine and the Docker Compose plugin.
- A DNS `A`/`AAAA` record for the public hostname pointing to the host.
- Inbound TCP ports 80 and 443 (and UDP 443 for HTTP/3) allowed through the host and cloud firewall.
- Enough disk space for PostgreSQL, Redis, and Caddy's persistent volumes.

The production Compose overlay runs Caddy as the only public service. It obtains and renews HTTPS certificates, routes `/api/*` and `/health` to FastAPI, and sends other paths to Next.js. The database, API, and Redis have no published host ports.

## Configure and launch

1. Copy `.env.production.example` to `.env.production`.
2. Set `DOMAIN`, `NEXT_PUBLIC_API_URL`, and `CORS_ORIGINS_RAW` to the same real HTTPS origin.
3. Generate distinct application secrets and a strong database password. Do not reuse the development `.env` values or commit `.env.production`.

   ```sh
   openssl rand -hex 32
   openssl rand -hex 32
   ```

4. Start the stack and wait for health checks:

   ```sh
   docker compose --env-file .env.production \
     -f docker-compose.yml -f docker-compose.production.yml up --build -d
   docker compose --env-file .env.production \
     -f docker-compose.yml -f docker-compose.production.yml ps
   ```

5. Confirm the HTTPS site, `https://$DOMAIN/health`, customer registration/login, and the staff/admin login. Provision the first privileged account interactively:

   ```sh
   docker compose --env-file .env.production \
     -f docker-compose.yml -f docker-compose.production.yml \
     exec backend python -m app.cli --role admin --email owner@example.com --name "Shop Owner"
   ```

   The command prompts for the password; do not put account passwords in command arguments.

The backend container applies Alembic migrations before starting. Back up PostgreSQL before deploying a release that changes schema. Pin image tags/digests and review dependency/build changes before production rollout; this repository's Compose file is a single-host deployment baseline, not a high-availability topology.

## Operations and recovery

- Check service health and recent logs:

  ```sh
  docker compose --env-file .env.production \
    -f docker-compose.yml -f docker-compose.production.yml ps
  docker compose --env-file .env.production \
    -f docker-compose.yml -f docker-compose.production.yml logs --tail=200 backend
  ```

- Back up and restore PostgreSQL with `pg_dump`/`pg_restore` from the database container or an approved backup system. Store backups outside the host and periodically test restores.
- Keep the PostgreSQL, Redis, and Caddy volumes persistent. Redis stores rate-limit counters; losing that volume clears counters, not wallet data.
- For rollback, stop the new release and redeploy the last known-good image only if its schema is compatible. Database migrations may not be safely reversible; restore the pre-deployment database backup when required.
- Rotate JWT and QR secrets deliberately. Changing either invalidates existing sessions or redemption QR codes; notify staff/customers and follow the business recovery procedure.
- Monitor disk usage, database backups, certificate renewal, and logs. Configure host-level firewalling and a supported Docker security update process.

## Local checks

```sh
cd backend
PYTHONPATH=. ../.venv/bin/pytest
cd ../frontend
corepack npm ci
corepack npm run lint
corepack npm run build
corepack npm run test:e2e
```

The browser tests expect the local Compose stack to be running at `http://127.0.0.1:3000` and `http://127.0.0.1:8000`.
