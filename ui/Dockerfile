# ══════════════════════════════════════════════════════════════════════════════
# Cortex Knowledge Assistant - Production Frontend Dockerfile
# ══════════════════════════════════════════════════════════════════════════════
# Multi-stage build: Node.js for building, Nginx for serving
# Author: Gonzalo Romero - DeepRat
# ══════════════════════════════════════════════════════════════════════════════

# ─────────────────────────────────────────────────────────────────────────────
# Stage 1: Builder - Build React application
# ─────────────────────────────────────────────────────────────────────────────
FROM node:20-alpine AS builder

WORKDIR /app

# Copy package files first for better caching
COPY package.json package-lock.json ./

# Install dependencies (use npm install to handle new deps)
RUN npm install

# Copy source code
COPY . .

# Set API base URL to empty for nginx proxy (relative paths)
# ARG is needed because Vite replaces env vars at build time
ARG VITE_API_BASE_URL=""
ENV VITE_API_BASE_URL=${VITE_API_BASE_URL}

# Demo domain configuration (banking, university, clinic)
ARG VITE_DEMO_DOMAIN="banking"
ENV VITE_DEMO_DOMAIN=${VITE_DEMO_DOMAIN}

# Demo mode configuration (none, fce_iuc, firstrun, banking_demo)
ARG VITE_DEMO_MODE="none"
ENV VITE_DEMO_MODE=${VITE_DEMO_MODE}

# Demo reset timer visibility (true/false)
ARG VITE_DEMO_RESET_ENABLED="false"
ENV VITE_DEMO_RESET_ENABLED=${VITE_DEMO_RESET_ENABLED}

# Build production bundle
RUN npm run build

# ─────────────────────────────────────────────────────────────────────────────
# Stage 2: Runtime - Serve with Nginx
# ─────────────────────────────────────────────────────────────────────────────
FROM nginx:alpine AS runtime

LABEL maintainer="DeepRatAI <deeprat.tec@gmail.com>" \
  version="0.1.0-beta" \
  description="Cortex Knowledge Assistant - Frontend UI"

# Copy custom nginx configuration
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Copy built assets from builder stage
COPY --from=builder /app/dist /usr/share/nginx/html

# Create non-root user for nginx
RUN chown -R nginx:nginx /usr/share/nginx/html && \
  chown -R nginx:nginx /var/cache/nginx && \
  chown -R nginx:nginx /var/log/nginx && \
  touch /var/run/nginx.pid && \
  chown -R nginx:nginx /var/run/nginx.pid

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
  CMD wget --no-verbose --tries=1 --spider http://localhost:80/ || exit 1

EXPOSE 80

# Run as non-root user
USER nginx

CMD ["nginx", "-g", "daemon off;"]
