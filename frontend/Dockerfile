FROM node:20.18-alpine AS build
WORKDIR /app
# Vite inlines VITE_* env vars at build time, so the backend URL must be
# passed as a build arg (not a runtime env var) for cloud builds where
# there's no local .env file, e.g. `docker build --build-arg
# VITE_API_BASE_URL=https://backend.example.com .`
ARG VITE_API_BASE_URL=""
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL
COPY package.json ./
RUN npm install
COPY . .
RUN npm run build

FROM nginx:1.27-alpine
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 80
