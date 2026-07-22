# syntax=docker/dockerfile:1.7
FROM python:3.13-slim AS builder

ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONDONTWRITEBYTECODE=1

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
WORKDIR /build
COPY requirements.txt ./
RUN pip install --upgrade pip && pip install --requirement requirements.txt

FROM python:3.13-slim AS runtime

ARG APP_HOME=/app
ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DJANGO_SETTINGS_MODULE=aigitgateway.settings.production \
    PORT=8000

RUN groupadd --gid 10001 app \
    && useradd --uid 10001 --gid app --create-home --home-dir /home/app app

COPY --from=builder /opt/venv /opt/venv
WORKDIR ${APP_HOME}
COPY --chown=app:app . ${APP_HOME}

RUN SECRET_KEY=build-only-key-64-characters-000000000000000000000000000000000 \
    DATABASE_URL=sqlite:////tmp/static-build.sqlite3 \
    APP_URL=http://localhost \
    python manage.py collectstatic --noinput \
    && chmod +x ${APP_HOME}/scripts/entrypoint.sh

USER app
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=25s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health/', timeout=3)" || exit 1

ENTRYPOINT ["/app/scripts/entrypoint.sh"]
CMD ["gunicorn", "--config", "gunicorn.conf.py", "aigitgateway.wsgi:application"]
