FROM node:24-alpine AS frontend
WORKDIR /src
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.12-slim AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8080
WORKDIR /app
COPY backend/ /tmp/backend/
RUN pip install --no-cache-dir /tmp/backend && rm -rf /tmp/backend
COPY backend/app/ /app/backend/app/
COPY --from=frontend /src/dist/ /app/frontend/dist/
WORKDIR /app/backend
RUN useradd --create-home --uid 10001 appuser && chown -R appuser:appuser /app
USER appuser
EXPOSE 8080
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT}"]

