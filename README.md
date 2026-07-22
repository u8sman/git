# AI Git Gateway

A focused Django service that lets AI coding tools push **completed file changes** directly to approved GitHub repositories without receiving your GitHub credential.

The product intentionally does only four things:

1. Register GitHub repositories as projects.
2. Issue project-scoped, revocable AI tokens.
3. Accept completed file changes through a small HTTP API and create a non-force Git commit.
4. Show token access and push history in a clean control panel.

## Interface

- Custom responsive dashboard with an AdminLTE-inspired information layout and original AI Git Gateway branding.
- Django Unfold for the advanced `/admin/` interface.
- django-allauth for browser login and logout.
- Public `/instructions/` page written for AI coding agents.
- Persistent dashboard warning while any AI token is active.

Public account registration is disabled. Only active staff users can enter the control panel.

## Security model

- An AI receives only an `aig_...` gateway token.
- The token secret is shown once and only its SHA-256 hash is stored.
- Tokens can be limited to selected projects and can expire or remain active until revoked.
- The GitHub App private key or server GitHub token stays inside the web service.
- Direct pushes are limited by each project's branch allowlist.
- Every GitHub ref update uses `force: false`.
- Unsafe paths, malformed branch names, duplicate paths, invalid Base64, unsupported file modes, oversized files, and stale expected heads are rejected.
- The gateway accepts files; it does not run AI-generated shell commands.

## Technology

- Python 3.13
- Django 5.2 LTS
- django-allauth
- Django Unfold
- PostgreSQL
- Gunicorn
- WhiteNoise
- Docker Compose

The settings structure follows the useful production conventions from Cookiecutter-Django—split local/test/production settings, environment-only secrets, immutable containers, and explicit health checks—without adding Celery, Redis, mail services, or other components this small gateway does not need.

## Local Python setup

```bash
python -m venv .venv
. .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env
set -a; . ./.env; set +a
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

Open `http://localhost:8000`.

## Local Docker setup

```bash
docker compose -f docker-compose.yml -f docker-compose.local.yml up --build
```

Open `http://localhost:8000` and sign in with:

```text
username: admin
password: change-me-now
```

Change that password immediately. The local override is for development only.

## Coolify deployment

See [COOLIFY.md](COOLIFY.md) for the complete deployment checklist.

The production Compose file is already prepared for Coolify:

- `web` is exposed internally on port `8000`, with no host port mapping.
- `db` remains private.
- Coolify magic variables generate the Django secret, database password, admin bootstrap password, and service URL.
- `/ready/` is used by the Compose health check.
- migrations run automatically before Gunicorn starts, with database-startup retries.
- static files are collected during the Docker image build.
- web and database logs use bounded Docker log rotation.
- the application container runs as a non-root user with a read-only filesystem, dropped Linux capabilities, and a writable `/tmp` tmpfs only.

## GitHub authentication

### GitHub App — recommended

Create a GitHub App with repository permissions:

- **Contents: Read and write**
- **Metadata: Read-only**

Install it only on repositories the gateway may access. Set the App ID, then provide the private key using **one** of these options. Base64 is recommended for Coolify because it avoids multiline-secret formatting issues.

```env
GITHUB_AUTH_MODE=app
GITHUB_APP_ID=123456
GITHUB_APP_PRIVATE_KEY_BASE64=<base64-of-the-complete-pem-file>
```

Generate the value locally without line wrapping:

```bash
base64 -w 0 github-app-private-key.pem
```

On macOS:

```bash
base64 < github-app-private-key.pem | tr -d '\n'
```

Raw multiline `GITHUB_APP_PRIVATE_KEY` and file-based `GITHUB_APP_PRIVATE_KEY_PATH` are also supported. Enter the installation ID when adding each project.

### Server token — simpler personal setup

Use a fine-grained GitHub token limited to the exact repositories and Contents read/write permission:

```env
GITHUB_AUTH_MODE=token
GITHUB_TOKEN=github_pat_xxx
```

The AI never receives this credential in either mode.

## AI API

### Discover allowed projects

```bash
curl https://gateway.example.com/api/v1/projects \
  -H "Authorization: Bearer $AI_GIT_TOKEN"
```

### Push completed files

```bash
curl -X POST https://gateway.example.com/api/v1/push \
  -H "Authorization: Bearer $AI_GIT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "project": "example",
    "branch": "main",
    "commit_message": "Finish requested feature",
    "files": [
      {"path": "src/app.py", "content": "print(\"done\")\n"},
      {"path": "old.py", "delete": true}
    ]
  }'
```

Use `content_base64` for binary files. Include `expected_head` to reject delivery if the branch changed after the AI read it.

The public pages are:

```text
/instructions/             Human-readable AI instructions
/api/v1/instructions       Machine-readable instructions
/health/                   Process health
/ready/                    Database readiness
```

## CLI helper

```bash
export AI_GIT_TOKEN='aig_...'
python cli/ai_push.py \
  --gateway https://gateway.example.com/api/v1 \
  --project example \
  --branch main \
  --message "Finish requested feature" \
  src/app.py templates/page.html
```

Add `--delete old.py` to delete a repository file.

## Tests and checks

```bash
pytest
ruff check .
python manage.py check
DJANGO_SETTINGS_MODULE=aigitgateway.settings.production \
  SECRET_KEY=test-only \
  DATABASE_URL=sqlite:////tmp/gateway-check.sqlite3 \
  APP_URL=https://gateway.example.com \
  python manage.py check --deploy
```

## Important operating rule

Create a separate AI token for each agent or device. Revoke it as soon as that job ends. The dashboard keeps an active-access warning visible until all tokens are revoked or expired. Token creation responses are marked `no-store`, and the plaintext secret is never persisted by Django.

## License

MIT
