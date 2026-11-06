# The edge (self-hosted installs, M3-5): Caddy for TLS and routing, with the
# widget's files built in and served from https://$API_DOMAIN/sdk/.
# Build context: fluid-buddha-sdk/ (see docker-compose.yml).
FROM node:24-alpine AS sdk
WORKDIR /sdk
COPY package.json package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY . .
RUN npm run build

FROM caddy:2-alpine
COPY --from=sdk /sdk/dist /srv/sdk
