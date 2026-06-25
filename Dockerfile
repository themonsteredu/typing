# Exam Studio — single-container image (Node studio + Python engine).
# Vercel-style serverless can't run this (needs Python + a long-running process +
# a writable filesystem), so we ship one container that has both runtimes.

# ---- Stage 1: build the Next.js studio (standalone output) ----
FROM node:22-bookworm-slim AS studio-build
WORKDIR /app/studio
RUN corepack enable
COPY studio/package.json ./
# No lockfile committed -> plain install; add one and switch to --frozen-lockfile for reproducible builds.
RUN pnpm install
COPY studio/ ./
RUN pnpm build

# ---- Stage 2: runtime with Node + Python ----
FROM node:22-bookworm-slim AS runtime
ENV PYTHONUNBUFFERED=1 \
    NODE_ENV=production \
    PORT=3020 \
    EXAM_STUDIO_ENGINE_DIR=/app/engine \
    PYTHON_BIN=/app/engine/.venv/bin/python

RUN apt-get update \
    && apt-get install -y --no-install-recommends python3 python3-venv python3-pip \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Python engine + virtualenv
COPY engine/ /app/engine/
RUN python3 -m venv /app/engine/.venv \
    && /app/engine/.venv/bin/pip install --no-cache-dir --upgrade pip \
    && /app/engine/.venv/bin/pip install --no-cache-dir -r /app/engine/requirements.txt

# Next.js standalone server + static assets
COPY --from=studio-build /app/studio/.next/standalone/ /app/
COPY --from=studio-build /app/studio/.next/static/ /app/studio/.next/static/
COPY --from=studio-build /app/studio/public/ /app/studio/public/

# Persist settings + license + work files here (mount a volume to keep them).
VOLUME ["/data"]
ENV HOME=/data \
    EXAM_STUDIO_SETTINGS=/data/.exam-studio/settings.json \
    EXAM_STUDIO_LICENSE=/data/.exam-studio/license.json

EXPOSE 3020
# Standalone server.js lives under the traced repo root layout.
CMD ["node", "studio/server.js"]
