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

# Dev stage: used by docker-compose.dev.yml for live-reload local development
# via the Vite dev server (with HMR) instead of a static nginx build. Not
# used by the production image below.
FROM node:20.18-alpine AS dev
WORKDIR /app
COPY package.json ./
RUN npm install
COPY . .
EXPOSE 5173
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0", "--port", "5173"]

FROM nginx:1.27-alpine
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 80
