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

# ---- Native core build stage ------------------------------------------
# Compiles the optional C/C++ tracking core (see docs/NATIVE_CORE.md). It lives
# in its own stage so the ~400MB of compiler toolchain never reaches the runtime
# image — only the resulting .so is copied across.
#
# cmake and a compiler are installed right here, so this stage always produces
# the library and the runtime COPY below always finds it. build_native.sh's
# exit-0-without-cmake path is for developer machines, not for this image — if
# the compile itself breaks, the image build should fail loudly rather than
# ship a silently slower deploy.
FROM python:3.11-slim AS native-build
RUN apt-get update && apt-get install -y --no-install-recommends build-essential cmake \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /build
COPY native/ ./native/
COPY scripts/build_native.sh ./scripts/
RUN sh scripts/build_native.sh

# ---- Python runtime -----------------------------------------------------
FROM python:3.11-slim

WORKDIR /app

# ffmpeg: yt-dlp needs it to merge YouTube's separate video/audio streams
# into one playable file for anything above the lowest pre-muxed quality —
# see backend/video/youtube.py.
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
COPY --from=frontend-build /app/frontend/dist ./frontend/dist
# After COPY . . so the freshly compiled library wins over anything a local
# build left in the context. backend/native/_loader.py looks here first.
COPY --from=native-build /build/native/build/libtrugrade_core.so ./native/build/

# Render (and most PaaS hosts) inject the port to bind via $PORT.
ENV PORT=8000
EXPOSE 8000

# --no-access-log: app/core/logging_config.py's RequestIDMiddleware logs a
# structured, request-ID-correlated line per request already — uvicorn's own
# plain-text access log would just be a redundant second copy of every line.
CMD ["sh", "-c", "python scripts/init_db.py; uvicorn backend.main:app --host 0.0.0.0 --port ${PORT} --no-access-log"]
