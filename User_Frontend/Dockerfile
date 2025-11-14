# # User_Frontend/Dockerfile — robust install (uses npm ci if lockfile exists)
# FROM node:20-alpine AS build
# WORKDIR /app

# # allow passing VITE_API_URL at build time
# ARG VITE_API_URL="/api"
# ENV VITE_API_URL=${VITE_API_URL}

# # copy package files (and lockfile if present)
# COPY package*.json ./

# # if package-lock.json exists -> npm ci, otherwise npm install
# RUN if [ -f package-lock.json ]; then \
#       echo "Found package-lock.json — running npm ci"; \
#       npm ci --loglevel=error; \
#     else \
#       echo "No package-lock.json — running npm install"; \
#       npm install --loglevel=error; \
#     fi

# # copy source and build
# COPY . .
# RUN npm run build

# # ---------- Serve with nginx ----------
# FROM nginx:stable-alpine
# WORKDIR /usr/share/nginx/html
# RUN rm -rf ./*
# COPY --from=build /app/dist .
# #COPY nginx.conf /etc/nginx/conf.d/default.conf

# ENV ADMIN_CLOUD_RUN_URL=""
# CMD ["/bin/sh","-c","if [ -n \"$ADMIN_CLOUD_RUN_URL\" ]; then sed -i \"s|window.__RAG_API_URL__ = ''|window.__RAG_API_URL__ = '$ADMIN_CLOUD_RUN_URL'|g\" /usr/share/nginx/html/index.html || true; fi && nginx -g 'daemon off;'"]

# Build stage
FROM node:20-alpine AS build
WORKDIR /app
ARG VITE_API_URL="/api"
ENV VITE_API_URL=${VITE_API_URL}

COPY package*.json ./
RUN if [ -f package-lock.json ]; then \
      npm ci --loglevel=error; \
    else \
      npm install --loglevel=error; \
    fi

COPY . .
RUN npm run build

# Serve with nginx
FROM nginx:stable-alpine
WORKDIR /usr/share/nginx/html
RUN rm -rf ./* && mkdir -p /tmp/nginx
COPY --from=build /app/dist .

RUN mkdir -p /tmp/nginx/client_temp /tmp/nginx/proxy_temp /tmp/nginx/fastcgi_temp \
 && chmod -R 0777 /tmp/nginx \
 && sed -i "/http[[:space:]]*{/a \
    \ \ client_body_temp_path /tmp/nginx/client_temp; \
    \ \ proxy_temp_path /tmp/nginx/proxy_temp; \
    \ \ fastcgi_temp_path /tmp/nginx/fastcgi_temp;" /etc/nginx/nginx.conf


ENV ADMIN_CLOUD_RUN_URL=""

# Use /tmp/nginx for temp files
RUN sed -i '1i client_body_temp_path /tmp/nginx/client_temp;\nproxy_temp_path /tmp/nginx/proxy_temp;\nfastcgi_temp_path /tmp/nginx/fastcgi_temp;' /etc/nginx/nginx.conf

CMD ["/bin/sh","-c","if [ -n \"$ADMIN_CLOUD_RUN_URL\" ]; then sed -i \"s|window.__RAG_API_URL__ = ''|window.__RAG_API_URL__ = '$ADMIN_CLOUD_RUN_URL'|g\" /usr/share/nginx/html/index.html || true; fi && nginx -g 'daemon off;'"]
