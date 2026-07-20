FROM node:22-alpine AS deps

RUN corepack enable && corepack prepare pnpm@11.13.1 --activate

WORKDIR /app

COPY package.json pnpm-lock.yaml pnpm-workspace.yaml ./
RUN pnpm install --frozen-lockfile --ignore-scripts

FROM node:22-alpine AS build

RUN corepack enable && corepack prepare pnpm@11.13.1 --activate

WORKDIR /app

COPY --from=deps /app/node_modules ./node_modules
COPY --from=deps /app/package.json /app/pnpm-lock.yaml /app/pnpm-workspace.yaml ./
COPY . .

ENV NODE_ENV=production

RUN pnpm exec nuxt prepare && pnpm build

FROM node:22-alpine AS runner

WORKDIR /app

ENV NODE_ENV=production \
  HOST=0.0.0.0 \
  PORT=3000 \
  NITRO_HOST=0.0.0.0 \
  NITRO_PORT=3000

COPY --from=build /app/.output ./.output

USER node

EXPOSE 3000

CMD ["node", ".output/server/index.mjs"]
