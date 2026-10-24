# Web app: build the Vite bundle with pnpm, serve it with nginx and proxy /api to the API app,
# so the browser only ever talks to one origin. Build context is the repo root.
FROM node:22-slim AS build
RUN npm install -g pnpm@12.3.4
WORKDIR /src
COPY pnpm-workspace.yaml pnpm-lock.yaml ./
COPY packages/contracts ./packages/contracts
COPY apps/web ./apps/web
RUN pnpm install --frozen-lockfile --filter web... && pnpm --filter web build

FROM nginx:1.27-alpine
# The nginx image runs envsubst on /etc/nginx/templates/*.template at start; API_UPSTREAM comes
# from the Container App's environment (https://<api fqdn>).
COPY infra/web/default.conf.template /etc/nginx/templates/default.conf.template
COPY --from=build /src/apps/web/dist /usr/share/nginx/html
EXPOSE 80
