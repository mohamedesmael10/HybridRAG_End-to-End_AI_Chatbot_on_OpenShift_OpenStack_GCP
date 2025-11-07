# User_Frontend/Dockerfile — robust install (uses npm ci if lockfile exists)
FROM node:20-alpine AS build
WORKDIR /app

# allow passing VITE_API_URL at build time
ARG VITE_API_URL="/api"
ENV VITE_API_URL=${VITE_API_URL}

# copy package files (and lockfile if present)
COPY package*.json ./

# if package-lock.json exists -> npm ci, otherwise npm install
RUN if [ -f package-lock.json ]; then \
      echo "Found package-lock.json — running npm ci"; \
      npm ci --loglevel=error; \
    else \
      echo "No package-lock.json — running npm install"; \
      npm install --loglevel=error; \
    fi

# copy source and build
COPY . .
RUN npm run build

# ---------- Serve with nginx ----------
FROM nginx:stable-alpine
WORKDIR /usr/share/nginx/html
RUN rm -rf ./*
COPY --from=build /app/dist .
COPY nginx.conf /etc/nginx/conf.d/default.conf

ENV ADMIN_CLOUD_RUN_URL=""
CMD ["/bin/sh","-c","if [ -n \"$ADMIN_CLOUD_RUN_URL\" ]; then sed -i \"s|window.__RAG_API_URL__ = ''|window.__RAG_API_URL__ = '$ADMIN_CLOUD_RUN_URL'|g\" /usr/share/nginx/html/index.html || true; fi && nginx -g 'daemon off;'"]
