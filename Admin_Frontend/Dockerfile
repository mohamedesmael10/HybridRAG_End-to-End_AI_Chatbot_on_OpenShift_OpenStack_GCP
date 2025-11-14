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


# after COPY --from=builder /app/dist /usr/share/nginx/html
RUN chmod -R a+rwX /usr/share/nginx/html \
 && mkdir -p /tmp/nginx/client_temp /tmp/nginx/proxy_temp /tmp/nginx/fastcgi_temp \
 && chmod -R 0777 /tmp/nginx \
 && sed -i "/http[[:space:]]*{/a \
    \ \ client_body_temp_path /tmp/nginx/client_temp; \
    \ \ proxy_temp_path /tmp/nginx/proxy_temp; \
    \ \ fastcgi_temp_path /tmp/nginx/fastcgi_temp;" /etc/nginx/nginx.conf

# Copy nginx configuration
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Runtime environment injection (replaces API URL dynamically)
ENV ADMIN_CLOUD_RUN_URL=""
CMD ["/bin/sh", "-c", "\
  if [ -n \"$ADMIN_CLOUD_RUN_URL\" ]; then \
    sed -i \"s|window.__RAG_API_URL__ = ''|window.__RAG_API_URL__ = '$ADMIN_CLOUD_RUN_URL'|g\" /usr/share/nginx/html/index.html; \
  fi && \
  nginx -g 'daemon off;'"]
