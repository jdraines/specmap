// Command api starts the specmap API server.
package main

import (
	"context"
	"fmt"
	"log/slog"
	"net/http"
	"os"
	"os/signal"
	"syscall"
	"time"

	"github.com/specmap/specmap/api/internal/config"
	"github.com/specmap/specmap/api/internal/server"
	"github.com/specmap/specmap/api/internal/store"
)

func main() {
	if err := run(); err != nil {
		slog.Error("fatal", "error", err)
		os.Exit(1)
	}
}

func run() error {
	cfg, err := config.Load()
	if err != nil {
		return fmt.Errorf("loading config: %w", err)
	}

	ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
	defer cancel()

	// Connect to database.
	st, err := store.New(ctx, cfg.DatabaseURL)
	if err != nil {
		return fmt.Errorf("connecting to database: %w", err)
	}
	defer st.Close()

	// Run migrations.
	slog.Info("running database migrations")
	if err := st.Migrate(cfg.DatabaseURL); err != nil {
		return fmt.Errorf("running migrations: %w", err)
	}

	// Build server.
	srv := server.New(cfg, st)
	httpServer := &http.Server{
		Addr:         fmt.Sprintf(":%d", cfg.Port),
		Handler:      srv.Handler(),
		ReadTimeout:  10 * time.Second,
		WriteTimeout: 30 * time.Second,
		IdleTimeout:  60 * time.Second,
	}

	// Graceful shutdown.
	errCh := make(chan error, 1)
	go func() {
		if cfg.TLSCert != "" && cfg.TLSKey != "" {
			slog.Info("server starting (TLS)", "port", cfg.Port, "base_url", cfg.BaseURL)
			errCh <- httpServer.ListenAndServeTLS(cfg.TLSCert, cfg.TLSKey)
		} else {
			slog.Info("server starting", "port", cfg.Port, "base_url", cfg.BaseURL)
			errCh <- httpServer.ListenAndServe()
		}
	}()

	quit := make(chan os.Signal, 1)
	signal.Notify(quit, syscall.SIGINT, syscall.SIGTERM)

	select {
	case sig := <-quit:
		slog.Info("shutting down", "signal", sig)
	case err := <-errCh:
		return fmt.Errorf("server error: %w", err)
	}

	shutdownCtx, shutdownCancel := context.WithTimeout(context.Background(), 10*time.Second)
	defer shutdownCancel()

	return httpServer.Shutdown(shutdownCtx)
}
