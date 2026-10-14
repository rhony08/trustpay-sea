FROM python:3.11-slim

WORKDIR /srv/api

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

COPY pyproject.toml ./
RUN pip install .

COPY alembic.ini ./
COPY alembic ./alembic
COPY app ./app
COPY tests ./tests

RUN pip install ".[dev]"

EXPOSE 8000

CMD ["sh", "-c", "python -m app.generate_dev_keys && alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000"]
