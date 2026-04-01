# Stage 1: Build frontend
FROM node:22-alpine AS frontend
WORKDIR /build
COPY web/package.json web/package-lock.json ./
RUN npm ci
COPY web/ ./
RUN npm run build

# Stage 2: Build Go binary with embedded frontend
FROM golang:1.25-alpine AS builder
RUN apk add --no-cache git
WORKDIR /build
COPY api/go.mod api/go.sum ./
RUN go mod download
COPY api/ ./
# Embed frontend build output into the static directory
COPY --from=frontend /build/dist/ ./cmd/api/static/
RUN CGO_ENABLED=0 GOOS=linux go build \
    -ldflags "-s -w -X main.Version=$(cat VERSION)" \
    -o /specmap-api ./cmd/api

# Stage 3: Minimal runtime
FROM alpine:3.21
RUN apk add --no-cache ca-certificates wget && \
    addgroup -S specmap && adduser -S specmap -G specmap
COPY --from=builder /specmap-api /usr/local/bin/specmap-api
USER specmap
EXPOSE 8080
ENTRYPOINT ["specmap-api"]
