# Three explicit build targets (research.md § 5):
#   dev     — development and debugging. NOT for production.
#   test    — automated testing and test dependencies. NOT for production.
#   runtime — application and runtime dependencies only. Production target.
#
# The "runtime" target MUST NOT contain test code or requirements_test.txt;
# scripts/image_content_check.sh asserts this (quickstart.md § 9.5, T111).

ARG PYTHON_IMAGE=python:3.14-slim-bookworm

FROM ghcr.io/astral-sh/uv:latest AS uv

FROM ${PYTHON_IMAGE} AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_LINK_MODE=copy \
    UV_SYSTEM_PYTHON=1 \
    UV_CACHE_DIR=/tmp/uv-cache

COPY --from=uv /uv /usr/local/bin/uv

# The system site-packages must be writable by the runtime user (uid 1000);
# the base image installs them root-owned, so a venv-owned prefix is used.
ENV UV_PYTHON=/usr/local UID=1000

# --- dev: dependencies + full source tree -----------------------------------
FROM base AS dev
USER root
RUN python -m venv /opt/venv && chown -R 1000:1000 /opt/venv
ENV PATH="/opt/venv/bin:${PATH}"
USER 1000:1000
WORKDIR /app
COPY --chown=1000:1000 requirements.txt ./
RUN uv pip install --python /opt/venv/bin/python -r requirements.txt
COPY --chown=1000:1000 . /app/
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]

# --- test: dev + test-only dependencies + the test suite ---------------------
FROM dev AS test
WORKDIR /app
COPY --chown=1000:1000 requirements_test.txt ./
RUN uv pip install --python /opt/venv/bin/python -r requirements_test.txt
COPY --chown=1000:1000 tests /app/tests
CMD ["python", "-m", "unittest", "discover", "-s", "tests"]

# --- runtime: runtime dependencies only --------------------------------------
FROM base AS runtime
WORKDIR /app
COPY --chown=1000:1000 requirements.txt ./
RUN uv pip install --system -r requirements.txt
COPY --chown=1000:1000 app /app/app
COPY --chown=1000:1000 main.py /app/main.py
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]