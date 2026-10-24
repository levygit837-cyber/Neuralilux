# Painel Next.js em três estágios: deps (npm ci) -> build (standalone) -> runtime mínimo, sem devDependencies.
# Contexto de build: frontend/
#
# NEXT_PUBLIC_API_URL (e NEXT_PUBLIC_WS_URL, se o Socket.IO ficar em outro host) é gravada no bundle do navegador e na CSP
# no `next build`: passe como build arg com a URL PÚBLICA da API. Trocar a URL exige rebuild.
# API_INTERNAL_URL (como o servidor do Next alcança a API, ex. http://api:8000) é lida em runtime: passe no `run`.

FROM node:24-alpine AS deps
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci


FROM node:24-alpine AS build
WORKDIR /app
ARG NEXT_PUBLIC_API_URL=http://localhost:8000
ARG NEXT_PUBLIC_WS_URL=
ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL \
    NEXT_PUBLIC_WS_URL=$NEXT_PUBLIC_WS_URL \
    NEXT_TELEMETRY_DISABLED=1
COPY --from=deps /app/node_modules ./node_modules
COPY . .
RUN npm run build


FROM node:24-alpine AS runtime
WORKDIR /app
ENV NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1 \
    HOSTNAME=0.0.0.0 \
    PORT=3000

# O usuário `node` (uid 1000) já existe na imagem.
COPY --from=build --chown=node:node /app/.next/standalone ./
COPY --from=build --chown=node:node /app/.next/static ./.next/static

USER node

EXPOSE 3000

HEALTHCHECK --interval=15s --timeout=5s --start-period=20s --retries=5 \
    CMD ["wget", "-q", "-O", "/dev/null", "http://127.0.0.1:3000/login"]

CMD ["node", "server.js"]
