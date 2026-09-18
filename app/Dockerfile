# Stage 1: Build
FROM node:22-alpine AS builder

WORKDIR /app

COPY package*.json ./
RUN npm ci

COPY . .
RUN npm run build


# Stage 2: Production dependencies
FROM node:22-alpine AS dependencies

WORKDIR /app

COPY package*.json ./
RUN npm ci --omit=dev


# Stage 3: Production runtime
FROM node:22-alpine AS production

WORKDIR /app

COPY --from=dependencies /app/node_modules ./node_modules
COPY --from=builder /app/dist ./dist

# npm/yarn/corepack are not needed at runtime
RUN rm -rf \
    /usr/local/lib/node_modules/npm \
    /usr/local/bin/npm \
    /usr/local/bin/npx \
    /opt/yarn* \
    /usr/local/bin/yarn \
    /usr/local/bin/yarnpkg \
    /usr/local/lib/node_modules/corepack \
    /usr/local/bin/corepack || true

EXPOSE 3000

CMD ["node", "dist/server.js"]