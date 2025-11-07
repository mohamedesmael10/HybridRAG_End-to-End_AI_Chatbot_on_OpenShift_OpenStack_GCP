# Stage 1: Build
FROM node:20-alpine AS builder
WORKDIR /app

COPY package*.json ./
RUN npm install --silent
COPY . .

ARG VITE_API_URL
ENV VITE_API_URL=$VITE_API_URL
RUN npm run build

# Stage 2: Serve with nginx
FROM nginx:stable-alpine
WORKDIR /usr/share/nginx/html

# Clean default nginx files and copy built files
RUN rm -rf ./*
COPY --from=builder /app/dist .

# Copy nginx configuration
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Runtime environment injection (replaces API URL dynamically)
ENV ADMIN_CLOUD_RUN_URL=""
CMD ["/bin/sh", "-c", "\
  if [ -n \"$ADMIN_CLOUD_RUN_URL\" ]; then \
    sed -i \"s|window.__RAG_API_URL__ = ''|window.__RAG_API_URL__ = '$ADMIN_CLOUD_RUN_URL'|g\" /usr/share/nginx/html/index.html; \
  fi && \
  nginx -g 'daemon off;'"]
