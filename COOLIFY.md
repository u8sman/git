# Deploy AI Git Gateway on Coolify

The repository includes a production `docker-compose.yml` designed for a Coolify Docker Compose resource.

## 1. Create the resource

1. Push this repository to the Git provider connected to Coolify.
2. In Coolify, create a new resource from that repository.
3. Choose the **Docker Compose** build pack.
4. Use `docker-compose.yml` as the Compose file.
5. Attach a domain to the `web` service on container port `8000`.

Do not publish the `db` service and do not add a host port mapping to the production file.

## 2. Review generated values

The Compose file asks Coolify to create and retain these values:

```text
SERVICE_URL_WEB_8000       Public URL routed to web:8000
SERVICE_HEX_64_DJANGO      Django SECRET_KEY
SERVICE_PASSWORD_POSTGRES  PostgreSQL password
SERVICE_PASSWORD_ADMIN     Initial dashboard admin password
```

The first administrator defaults to username `admin`. You can change it with `DJANGO_SUPERUSER_USERNAME` before the first deployment.

After the first successful sign-in:

1. Change the administrator password.
2. Set `CREATE_SUPERUSER=0`.
3. Keep `RESET_SUPERUSER_PASSWORD=0` unless you deliberately need a recovery reset.

The bootstrap script never resets an existing password unless `RESET_SUPERUSER_PASSWORD=1`.

## 3. Configure GitHub access

### Recommended: GitHub App

Add these secret environment variables in Coolify:

```env
GITHUB_AUTH_MODE=app
GITHUB_APP_ID=123456
GITHUB_APP_PRIVATE_KEY_BASE64=<base64-of-the-complete-pem-file>
```

Base64 is the recommended option because it avoids whitespace and multiline parsing problems in deployment environment variables. Generate it locally without wrapping:

```bash
base64 -w 0 github-app-private-key.pem
```

On macOS:

```bash
base64 < github-app-private-key.pem | tr -d '\n'
```

The gateway decodes the value in memory at startup. The decoded private key is never written to the database. A raw multiline `GITHUB_APP_PRIVATE_KEY` remains supported when preferred; no private-key volume is required.

The GitHub App needs:

```text
Repository permissions
- Contents: Read and write
- Metadata: Read-only
```

Install the app only on repositories that may receive code. Add the relevant installation ID to each gateway project.

### Alternative: fine-grained token

```env
GITHUB_AUTH_MODE=token
GITHUB_TOKEN=github_pat_xxx
```

Restrict the token to the exact repositories and the minimum Contents read/write permission.

## 4. Deploy

Deploy the stack. Startup proceeds in this order:

1. PostgreSQL becomes healthy.
2. Django migrations run.
3. The initial administrator is created when enabled and a password exists.
4. Gunicorn starts.
5. Coolify checks `http://web:8000/ready/` through the container health check.

Migration startup retries are controlled by `MIGRATION_MAX_ATTEMPTS` (default `12`). Set `MIGRATE_ON_START=0` only when migrations are run as a separate release command.

The main service should become healthy only after both the app and database are ready.

## 5. First login

Open the assigned domain and sign in with:

```text
username: value of DJANGO_SUPERUSER_USERNAME (default: admin)
password: value of SERVICE_PASSWORD_ADMIN
```

Then:

1. Add a project.
2. Enable direct push and set its allowed branch patterns.
3. Create a project-scoped agent token.
4. Copy the secret once.
5. Give the AI the public `/instructions/` page and the token.
6. Revoke the token when the AI finishes.

## Production settings

Recommended environment values:

```env
TIME_ZONE=Europe/London
WEB_CONCURRENCY=2
GUNICORN_THREADS=2
ALLAUTH_TRUSTED_PROXY_COUNT=1
SECURE_SSL_REDIRECT=0
SECURE_HSTS_SECONDS=0
```

`APP_URL` is populated from `SERVICE_URL_WEB_8000`. When the domain uses HTTPS, Django automatically marks session and CSRF cookies secure.

After HTTPS is confirmed and stable, you may enable:

```env
SECURE_SSL_REDIRECT=1
SECURE_HSTS_SECONDS=31536000
```

Enable HSTS only when the domain and all required subdomains are permanently HTTPS.

## Persistent data and backups

All durable application data is in PostgreSQL under the named volume:

```text
postgres_data
```

Configure Coolify backups for the PostgreSQL service or volume. The web image is disposable and contains no required runtime state.

Back up before Django or PostgreSQL version upgrades.

## Health endpoints

```text
/health/  Confirms the Django process responds
/ready/   Confirms Django can query the database
```

The Dockerfile and Compose stack include health checks. No `curl` package is required; the check uses Python's standard library.

## Updates and rollback

For a normal update:

1. Push a new commit to the deployment branch.
2. Let Coolify rebuild the immutable image.
3. Migrations run automatically at container start.
4. Coolify routes traffic after the health check passes.

For rollback, redeploy a previous Git commit. Database migrations should be designed to remain backward compatible when a fast application rollback may be needed.

## Troubleshooting

### Invalid host or CSRF errors

Confirm `SERVICE_URL_WEB_8000` contains the exact external URL, including `https://`, and that Coolify routes the domain to the `web` service on port `8000`.

### Login redirects repeatedly

Confirm the proxy sends `X-Forwarded-Proto` and keep:

```env
ALLAUTH_TRUSTED_PROXY_COUNT=1
```

### GitHub App pushes fail

Check:

- `GITHUB_APP_ID` is the numeric App ID, not the client ID.
- the decoded private key includes its BEGIN/END lines.
- `GITHUB_APP_PRIVATE_KEY_BASE64` contains no spaces or line breaks.
- the app is installed on the target repository.
- the project's installation ID is correct.
- Contents permission is read/write.
- the target branch matches the project's branch allowlist.
- GitHub branch protection permits the app to push.

## Container limits and logs

The production stack runs the web container as a non-root user with a read-only root filesystem, no added Linux capabilities, a process limit, and a small writable `/tmp`. Docker logs are bounded to three 10 MB files per service so a noisy deployment cannot fill the host indefinitely.
