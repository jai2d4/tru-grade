# ---- Frontend build stage --------------------------------------------
# Produces frontend/dist/ (the Vite build). backend/main.py serves it once
# every router is registered — see the comment there for why it has to be
# that entrypoint, not app/main.py.
FROM node:20-slim AS frontend-build
WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
# Baked into the JS bundle at build time (Vite only reads import.meta.env.VITE_*
# at build time, never at runtime) and sent back as the X-API-Key header on
# every request — see frontend/src/api/client.ts. Render passes dashboard env
# vars through as Docker build args automatically; a local `docker build`
# needs `--build-arg VITE_API_KEY=...` explicitly, or the bundle just omits
# the header, matching the frictionless no-auth local-dev default.
ARG VITE_API_KEY
ENV VITE_API_KEY=$VITE_API_KEY
RUN npm run build

# ---- Python runtime -----------------------------------------------------
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
COPY --from=frontend-build /app/frontend/dist ./frontend/dist

# Render (and most PaaS hosts) inject the port to bind via $PORT.
ENV PORT=8000
EXPOSE 8000

CMD ["sh", "-c", "python scripts/init_db.py; uvicorn backend.main:app --host 0.0.0.0 --port ${PORT}"]
