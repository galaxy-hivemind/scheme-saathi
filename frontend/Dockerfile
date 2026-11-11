# Scheme Saathi — Production Frontend Dockerfile
# Stage 1: Build React + Vite TypeScript SPA
FROM node:20-slim AS builder

WORKDIR /app

# Optimize Node memory allocation for container build environments
ENV NODE_OPTIONS="--max-old-space-size=1024"

# Copy dependency manifests and install exact dependencies
COPY package.json package-lock.json ./
RUN npm ci

# Copy source code and config files
COPY . .

# Set default API base URL for same-origin reverse proxy via Nginx
ARG VITE_API_BASE_URL=/api/v1
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL

# Build production bundle
RUN npm run build

# Stage 2: Serve optimized assets with Nginx Alpine
FROM nginx:1.27-alpine

# Remove default Nginx welcome site
RUN rm -rf /usr/share/nginx/html/*

# Copy built static assets from builder stage
COPY --from=builder /app/dist /usr/share/nginx/html

# Copy custom Nginx configuration with reverse proxy and SPA routing
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

# Healthcheck monitoring Nginx web server
HEALTHCHECK --interval=30s --timeout=3s --retries=3 \
    CMD wget -qO- http://127.0.0.1/ || exit 1

CMD ["nginx", "-g", "daemon off;"]
