# Copyright (c) 2026 Document Review Contributors
# SPDX-License-Identifier: MIT

FROM node:22-bookworm-slim AS build

WORKDIR /work
COPY web/package.json web/package-lock.json ./
RUN npm ci

COPY web ./
RUN npm run build

FROM nginx:1.27-alpine AS runtime
COPY web/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /work/dist /usr/share/nginx/html

EXPOSE 80

HEALTHCHECK --interval=10s --timeout=3s --start-period=5s --retries=5 \
    CMD ["wget", "-qO-", "http://127.0.0.1/health"]
