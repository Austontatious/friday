# syntax=docker/dockerfile:1

FROM node:20-alpine AS build
WORKDIR /app

ARG REACT_APP_SKETCHMATH_ENABLED=0
ENV REACT_APP_SKETCHMATH_ENABLED=${REACT_APP_SKETCHMATH_ENABLED}

COPY frontend/package.json frontend/package-lock.json /app/
RUN npm ci --legacy-peer-deps

COPY frontend/ /app/
# CRA build
RUN npm run build

FROM nginx:1.27-alpine AS prod
# Nginx config
COPY frontend/nginx.conf /etc/nginx/conf.d/default.conf
# Static build output
COPY --from=build /app/build /usr/share/nginx/html

EXPOSE 8080
CMD ["nginx", "-g", "daemon off;"]
