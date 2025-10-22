# ---- Stage 1: build React app ----
FROM node:20-alpine AS build         
WORKDIR /app                        
COPY package.json package-lock.json* ./   
RUN npm ci --silent                  
COPY . .                             
RUN npm run build                    

# ---- Stage 2: Nginx to serve static site ----
FROM nginx:stable-alpine             
COPY --from=build /app/dist /usr/share/nginx/html   
COPY nginx.conf /etc/nginx/conf.d/default.conf       


ENV VITE_API_URL=""
CMD ["/bin/sh","-c","if [ -n \"$VITE_API_URL\" ]; then sed -i \"s|window.__RAG_API_URL__ = ''|window.__RAG_API_URL__ = '$VITE_API_URL'|g\" /usr/share/nginx/html/index.html; fi && nginx -g 'daemon off;'"]

