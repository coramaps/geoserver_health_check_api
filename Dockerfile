
# The builder image, used to build the virtual environment
FROM python:3.12-bullseye AS builder

RUN pip install poetry==1.8.3

ENV POETRY_NO_INTERACTION=1 \
    POETRY_VIRTUALENVS_IN_PROJECT=1 \
    POETRY_VIRTUALENVS_CREATE=1 \
    POETRY_CACHE_DIR=/tmp/poetry_cache

WORKDIR /app

COPY pyproject.toml ./
RUN touch README.md

RUN poetry install --no-root && rm -rf $POETRY_CACHE_DIR

# The runtime image, used to just run the code provided its virtual environment
FROM python:3.12-bullseye AS runtime

ENV VIRTUAL_ENV=/app/.venv \
    PATH="/app/.venv/bin:$PATH" \
    TZ="UTC"

COPY --from=builder ${VIRTUAL_ENV} ${VIRTUAL_ENV}

RUN apt-get update && apt-get -y install cron nano && \
    ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

WORKDIR /app

CMD bash -c 'python3 -m uvicorn api.main:app --host 0.0.0.0 --log-level=debug --workers=8'