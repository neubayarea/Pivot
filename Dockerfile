# One image, one process: API + WebSocket + worker + simulator, and the built web app on the same port
# (pivot_api.single, docs/deploy-oracle.md). Builds on amd64 and arm64 (Oracle Ampere).

# --- web: pnpm --filter web build -> /web/apps/web/dist
FROM node:22-slim AS web
RUN npm install -g pnpm@12.3.4
WORKDIR /web
COPY pnpm-workspace.yaml pnpm-lock.yaml ./
COPY packages/contracts/package.json ./packages/contracts/
COPY apps/web/package.json ./apps/web/
RUN pnpm install --frozen-lockfile --filter web...
COPY packages/contracts ./packages/contracts
COPY apps/web ./apps/web
# web tests read a frozen recorded match (eval/frozen), and tsc checks them too
COPY eval/fixtures ./eval/fixtures
COPY eval/frozen ./eval/frozen
RUN pnpm --filter web build

# --- app: the Python workspace, plus the web build as static files
FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:0.9 /uv /usr/local/bin/uv

WORKDIR /app
ENV UV_LINK_MODE=copy UV_COMPILE_BYTECODE=1

COPY pyproject.toml uv.lock ./
COPY packages ./packages
COPY apps ./apps
COPY eval/fixtures ./eval/fixtures
RUN uv sync --frozen --no-dev --package pivot-api
COPY --from=web /web/apps/web/dist ./web

ENV PATH="/app/.venv/bin:$PATH" HOST=0.0.0.0 PORT=8000 PIVOT_WEB_DIST=/app/web \
    PIVOT_DEMO_FIXTURE=/app/eval/fixtures/demo-1021.json
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=3s CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/healthz')"
CMD ["python", "-m", "pivot_api.single"]
