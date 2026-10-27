# Web image. NOT BUILT OR TESTED in the repository's development environment (no Docker available).
# Build from apps/web:  docker build --build-arg LUMIANT_API_ORIGIN=http://api:8000 -t lumiant-web .
FROM node:22-alpine AS build
RUN corepack enable
WORKDIR /app
COPY package.json pnpm-lock.yaml pnpm-workspace.yaml ./
RUN pnpm install --frozen-lockfile
COPY . .
# The API origin is baked into the rewrite at build time (next.config.ts).
ARG LUMIANT_API_ORIGIN=http://api:8000
ENV LUMIANT_API_ORIGIN=$LUMIANT_API_ORIGIN NEXT_TELEMETRY_DISABLED=1
RUN pnpm build

FROM node:22-alpine
RUN corepack enable && addgroup -S lumiant && adduser -S lumiant -G lumiant
WORKDIR /app
ENV NODE_ENV=production NEXT_TELEMETRY_DISABLED=1
COPY --from=build --chown=lumiant:lumiant /app /app
USER lumiant
EXPOSE 3000
CMD ["pnpm", "start", "--port", "3000"]
