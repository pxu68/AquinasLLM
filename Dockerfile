FROM python:3.12-slim

WORKDIR /app

RUN pip install --no-cache-dir uv

COPY pyproject.toml README.md ./
COPY app ./app
COPY data ./data
COPY tests ./tests
COPY docs ./docs
COPY alembic.ini ./
COPY alembic ./alembic

RUN uv pip install --system -e ".[dev]"

EXPOSE 8000

COPY docker-entrypoint.sh /docker-entrypoint.sh
RUN sed -i 's/\r$//' /docker-entrypoint.sh && chmod +x /docker-entrypoint.sh

ENTRYPOINT ["/bin/sh", "/docker-entrypoint.sh"]
