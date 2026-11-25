# The marketing site as a container (production: deploy/azure, docs/deployment).
#
# NEXT_PUBLIC_* values are compiled into the JavaScript, so they are build arguments:
#   docker build --build-arg NEXT_PUBLIC_FB_LOADER_URL=https://gateway.fluidbuddha.com/widget/loader.js \
#                --build-arg NEXT_PUBLIC_FB_KEY=fbk_... -t fluidbuddha-website .
# Without a key, Ask Pragya runs its scripted preview instead of the real agent.
FROM node:24-alpine AS deps
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci --no-audit --no-fund

FROM node:24-alpine AS build
WORKDIR /app
ARG NEXT_PUBLIC_CONSOLE_URL=https://app.fluidbuddha.com
ARG NEXT_PUBLIC_FB_LOADER_URL=
ARG NEXT_PUBLIC_FB_KEY=
ENV NEXT_PUBLIC_CONSOLE_URL=$NEXT_PUBLIC_CONSOLE_URL \
    NEXT_PUBLIC_FB_LOADER_URL=$NEXT_PUBLIC_FB_LOADER_URL \
    NEXT_PUBLIC_FB_KEY=$NEXT_PUBLIC_FB_KEY \
    NEXT_OUTPUT=standalone \
    NEXT_TELEMETRY_DISABLED=1
COPY --from=deps /app/node_modules ./node_modules
COPY . .
RUN npm run build

FROM node:24-alpine
WORKDIR /app
ENV NODE_ENV=production NEXT_TELEMETRY_DISABLED=1 PORT=3000 HOSTNAME=0.0.0.0
RUN addgroup -S app && adduser -S app -G app
COPY --from=build --chown=app:app /app/.next/standalone ./
COPY --from=build --chown=app:app /app/.next/static ./.next/static
COPY --from=build --chown=app:app /app/public ./public
USER app
EXPOSE 3000
HEALTHCHECK --interval=15s --timeout=4s --start-period=20s --retries=5 \
  CMD wget -qO- http://127.0.0.1:3000/robots.txt >/dev/null || exit 1
CMD ["node", "server.js"]
