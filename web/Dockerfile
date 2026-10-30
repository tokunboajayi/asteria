# Asteria console. Build from the repository root:
#   docker build -f web/Dockerfile --build-arg NEXT_PUBLIC_API_URL=https://api.example.com -t asteria-web .
# NEXT_PUBLIC_ values are compiled into the browser bundle: never pass a secret here.
# The Cesium ion token must be read-only (assets:read) and restricted to your console's URL.
FROM node:22-slim AS build
WORKDIR /app/web
COPY web/package.json web/package-lock.json ./
COPY web/scripts ./scripts
RUN npm ci
COPY web/ ./
ARG NEXT_PUBLIC_API_URL=http://127.0.0.1:8000
ARG NEXT_PUBLIC_CESIUM_ION_TOKEN=
ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL \
    NEXT_PUBLIC_CESIUM_ION_TOKEN=$NEXT_PUBLIC_CESIUM_ION_TOKEN \
    NEXT_TELEMETRY_DISABLED=1
RUN npm run build && npm prune --omit=dev

FROM node:22-slim AS app
WORKDIR /app/web
ENV NODE_ENV=production NEXT_TELEMETRY_DISABLED=1
COPY --from=build --chown=node:node /app/web ./
USER node
EXPOSE 3000
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s \
  CMD node -e "fetch('http://127.0.0.1:3000').then(r=>process.exit(r.ok?0:1)).catch(()=>process.exit(1))"
CMD ["npm", "start"]
