FROM python:3.12-slim AS base
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY pyproject.toml ./
COPY packages ./packages
RUN pip install --no-cache-dir .
RUN useradd --create-home --uid 10001 safer && mkdir /results && chown safer /results
USER safer
ENTRYPOINT ["python", "-m", "safer_sim"]

FROM base AS test
USER root
RUN pip install --no-cache-dir '.[dev]'
COPY tests ./tests
USER safer
ENV PYTEST_ADDOPTS="-p no:cacheprovider"
ENTRYPOINT ["python", "-m", "pytest"]
