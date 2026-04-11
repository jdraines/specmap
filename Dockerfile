FROM node:22-alpine AS frontend
WORKDIR /build
COPY web/package.json web/package-lock.json ./
RUN npm ci
COPY web/ ./
RUN npm run build

FROM python:3.12-slim
WORKDIR /app
COPY core/ /app/core/
RUN pip install --no-cache-dir /app/core/
COPY --from=frontend /build/dist/ /app/static/
EXPOSE 8080
CMD ["specmap", "serve", "--static-dir", "/app/static"]
