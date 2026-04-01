package server

import (
	"context"
	"crypto/hmac"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"io"
	"log/slog"
	"net/http"
	"strings"
	"time"
)

const maxWebhookBodySize = 5 * 1024 * 1024 // 5MB

// webhookPayload contains the common fields across webhook event types.
type webhookPayload struct {
	Action       string              `json:"action"`
	Installation webhookInstallation `json:"installation"`
}

type webhookInstallation struct {
	ID                  int64              `json:"id"`
	Account             webhookAccount     `json:"account"`
	RepositorySelection string             `json:"repository_selection"`
	SuspendedAt         *time.Time         `json:"suspended_at"`
}

type webhookAccount struct {
	Login string `json:"login"`
	Type  string `json:"type"`
}

// handleWebhook receives and processes GitHub webhook events.
func (s *Server) handleWebhook(w http.ResponseWriter, r *http.Request) {
	body, err := io.ReadAll(io.LimitReader(r.Body, maxWebhookBodySize))
	if err != nil {
		writeError(w, http.StatusBadRequest, "reading request body")
		return
	}

	if !s.verifyWebhookSignature(body, r.Header.Get("X-Hub-Signature-256")) {
		writeError(w, http.StatusUnauthorized, "invalid signature")
		return
	}

	event := r.Header.Get("X-GitHub-Event")
	slog.Info("webhook received", "event", event)

	switch event {
	case "installation":
		s.handleInstallationEvent(body)
	case "installation_repositories":
		s.handleInstallationRepositoriesEvent(body)
	default:
		slog.Info("webhook event ignored", "event", event)
	}

	w.WriteHeader(http.StatusOK)
	w.Write([]byte(`{"ok":true}`))
}

// verifyWebhookSignature validates the HMAC-SHA256 signature from GitHub.
func (s *Server) verifyWebhookSignature(body []byte, signature string) bool {
	if !strings.HasPrefix(signature, "sha256=") {
		return false
	}
	sigBytes, err := hex.DecodeString(strings.TrimPrefix(signature, "sha256="))
	if err != nil {
		return false
	}

	mac := hmac.New(sha256.New, []byte(s.cfg.GitHubWebhookSecret))
	mac.Write(body)
	expected := mac.Sum(nil)

	return hmac.Equal(sigBytes, expected)
}

// handleInstallationEvent processes installation created/deleted/suspend/unsuspend events.
func (s *Server) handleInstallationEvent(body []byte) {
	var payload webhookPayload
	if err := json.Unmarshal(body, &payload); err != nil {
		slog.Error("parsing installation event", "error", err)
		return
	}

	ctx := contextForWebhook()
	inst := payload.Installation

	switch payload.Action {
	case "created":
		err := s.store.UpsertInstallation(ctx, inst.ID, inst.Account.Login, inst.Account.Type, inst.RepositorySelection)
		if err != nil {
			slog.Error("upserting installation", "github_id", inst.ID, "error", err)
			return
		}
		slog.Info("installation created", "github_id", inst.ID, "account", inst.Account.Login)

	case "deleted":
		err := s.store.DeleteInstallation(ctx, inst.ID)
		if err != nil {
			slog.Error("deleting installation", "github_id", inst.ID, "error", err)
			return
		}
		slog.Info("installation deleted", "github_id", inst.ID, "account", inst.Account.Login)

	case "suspend":
		err := s.store.SuspendInstallation(ctx, inst.ID)
		if err != nil {
			slog.Error("suspending installation", "github_id", inst.ID, "error", err)
			return
		}
		slog.Info("installation suspended", "github_id", inst.ID, "account", inst.Account.Login)

	case "unsuspend":
		err := s.store.UnsuspendInstallation(ctx, inst.ID)
		if err != nil {
			slog.Error("unsuspending installation", "github_id", inst.ID, "error", err)
			return
		}
		slog.Info("installation unsuspended", "github_id", inst.ID, "account", inst.Account.Login)

	default:
		slog.Info("installation action ignored", "action", payload.Action)
	}
}

// installationReposPayload has the fields specific to installation_repositories events.
type installationReposPayload struct {
	Action              string `json:"action"`
	RepositoriesAdded   []struct{ FullName string `json:"full_name"` } `json:"repositories_added"`
	RepositoriesRemoved []struct{ FullName string `json:"full_name"` } `json:"repositories_removed"`
}

// handleInstallationRepositoriesEvent logs repo additions/removals.
func (s *Server) handleInstallationRepositoriesEvent(body []byte) {
	var payload installationReposPayload
	if err := json.Unmarshal(body, &payload); err != nil {
		slog.Error("parsing installation_repositories event", "error", err)
		return
	}

	for _, r := range payload.RepositoriesAdded {
		slog.Info("repository added to installation", "repo", r.FullName)
	}
	for _, r := range payload.RepositoriesRemoved {
		slog.Info("repository removed from installation", "repo", r.FullName)
	}
}

// contextForWebhook returns a context with a timeout for webhook processing.
func contextForWebhook() context.Context {
	ctx, _ := context.WithTimeout(context.Background(), 30*time.Second)
	return ctx
}
