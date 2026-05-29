# ---- Stage 1: build the PWA ----
FROM node:22-slim AS frontend
WORKDIR /build
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# ---- Stage 2: backend runtime (serves the built PWA + API + runs the poller) ----
FROM python:3.11-slim
WORKDIR /app/backend

COPY backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ ./
# main.py looks for the build at <repo>/frontend/dist, i.e. /app/frontend/dist here.
COPY --from=frontend /build/dist /app/frontend/dist

# SQLite lives on a persistent volume mounted at /data (see fly.toml).
ENV DATABASE_URL=sqlite:////data/moneymoney.db
ENV POLL_INTERVAL_SECONDS=60

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
