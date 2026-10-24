# One Python image for api, worker and simulator. PACKAGE picks the uv workspace member to
# install and MODULE the `python -m` entry point; the defaults build the API.
# Not size-optimised yet (see A01 follow-ups).
FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:0.9 /uv /usr/local/bin/uv

ARG PACKAGE=pivot-api
ARG MODULE=pivot_api

WORKDIR /app
ENV UV_LINK_MODE=copy UV_COMPILE_BYTECODE=1

COPY pyproject.toml uv.lock ./
COPY packages ./packages
COPY apps ./apps
RUN uv sync --frozen --no-dev --package ${PACKAGE}

ENV PATH="/app/.venv/bin:$PATH" HOST=0.0.0.0 PORT=8000 PIVOT_MODULE=${MODULE}
EXPOSE 8000
CMD ["sh", "-c", "exec python -m \"$PIVOT_MODULE\""]
