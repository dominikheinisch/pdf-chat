# syntax=docker/dockerfile:1
FROM python:3.13-slim

COPY --from=ghcr.io/astral-sh/uv:0.13.0 /uv /uvx /bin/

# Match the host user so files written through bind mounts stay owned by you.
ARG UID=1000
ARG GID=1000
RUN groupadd --non-unique --gid "$GID" app \
    && useradd --non-unique --uid "$UID" --gid "$GID" --create-home app \
    && install -d -o app -g app /app /opt/venv

# The venv lives outside /app so bind-mounting the repo over /app doesn't hide it.
ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONPATH=/app/src \
    PYTHONUNBUFFERED=1 \
    UV_PROJECT_ENVIRONMENT=/opt/venv \
    UV_LINK_MODE=copy

USER app
WORKDIR /app

# Dependencies first, so source edits don't invalidate this layer.
RUN --mount=type=cache,target=/home/app/.cache/uv,uid=$UID,gid=$GID \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    uv sync --locked

COPY --chown=app:app . .

# --headless: no browser to open inside a container.
EXPOSE 8000
CMD ["chainlit", "run", "src/app.py", "--headless", "--host", "0.0.0.0", "--port", "8000"]
