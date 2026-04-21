FROM node:22-alpine AS frontend
WORKDIR /build
COPY web/package.json web/package-lock.json ./
RUN npm ci
COPY web/ ./
RUN npm run build

FROM python:3.12-slim
WORKDIR /app
COPY pyproject.toml hatch_build.py ./
COPY src/ ./src/
RUN pip install --no-cache-dir .
COPY --from=frontend /build/dist/ /app/static/
RUN useradd -r -s /bin/false specmap && chown -R specmap:specmap /app
USER specmap
EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8080/healthz')"
CMD ["specmap", "serve", "--host", "0.0.0.0", "--static-dir", "/app/static"]
