FROM golang:1.26-alpine AS builder

WORKDIR /src

RUN apk add --no-cache ca-certificates git

COPY go.mod go.sum ./
RUN go mod download

COPY . .

RUN CGO_ENABLED=0 GOOS=linux \
  go build -trimpath -ldflags="-s -w" -o /out/api ./cmd/api

FROM alpine:3.22

RUN apk add --no-cache ca-certificates tzdata \
  && adduser -D -H -u 10001 appuser

WORKDIR /app

COPY --from=builder /out/api /app/api

RUN mkdir -p /workspace/uploads \
  && chown -R appuser:appuser /workspace /app

USER appuser

ENV PORT=8080 \
  SCANEXAM_WORKSPACE=/workspace \
  SCANEXAM_UPLOADS_DIR=uploads

EXPOSE 8080

CMD ["/app/api"]
