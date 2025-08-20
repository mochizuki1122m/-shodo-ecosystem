# Multi-stage optimized React Frontend
FROM node:20-alpine AS builder

# Build tools and security
RUN apk add --no-cache \
    git \
    python3 \
    make \
    g++ \
    && addgroup -g 1000 -S appuser \
    && adduser -u 1000 -S appuser -G appuser

WORKDIR /app

# Node.js optimizations
ENV NODE_ENV=production \
    NPM_CONFIG_CACHE=/tmp/.npm \
    NPM_CONFIG_UPDATE_NOTIFIER=false \
    NPM_CONFIG_FUND=false \
    NPM_CONFIG_AUDIT=false

# Install dependencies
COPY package*.json ./
RUN npm ci --only=production --silent \
    && npm cache clean --force

# Copy source code
COPY --chown=appuser:appuser . .

# Build application
RUN npm run build

# Production runtime with Nginx
FROM nginx:alpine AS production

# Security updates
RUN apk upgrade --no-cache \
    && apk add --no-cache \
    tini \
    curl \
    && addgroup -g 1000 -S appuser \
    && adduser -u 1000 -S appuser -G appuser

# Copy built application
COPY --from=builder /app/build /usr/share/nginx/html

# Copy optimized nginx configuration
COPY nginx.conf /etc/nginx/nginx.conf

# Create required directories
RUN mkdir -p /var/cache/nginx /var/log/nginx \
    && chown -R appuser:appuser /var/cache/nginx /var/log/nginx /usr/share/nginx/html \
    && chmod -R 755 /usr/share/nginx/html

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD curl -f http://localhost:80/health || exit 1

# Security: Switch to non-root user
USER appuser

# Use tini as init system
ENTRYPOINT ["/sbin/tini", "--"]

# Start nginx
CMD ["nginx", "-g", "daemon off;"]

# Development target
FROM node:20-alpine AS development

RUN addgroup -g 1000 -S appuser \
    && adduser -u 1000 -S appuser -G appuser

WORKDIR /app

# Development dependencies
COPY package*.json ./
RUN npm install

# Copy source code
COPY --chown=appuser:appuser . .

# Security: Switch to non-root user
USER appuser

EXPOSE 3000

# Development server with hot reload
CMD ["npm", "start"]