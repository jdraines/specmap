"""Reusable code file content for functional tests.

All constants intentionally omit trailing newlines so that Python and Go
produce identical code-target hashes (Go's strings.Split + strings.Join
drops the trailing empty element that a final \\n creates).
"""

AUTH_GO = """\
package auth

import (
    "crypto/aes"
    "time"
)

// SessionStore manages authentication tokens.
type SessionStore struct {
    tokens map[string]*Token
    ttl    time.Duration
}

// NewSessionStore creates a new session store with a 24h TTL.
func NewSessionStore() *SessionStore {
    return &SessionStore{
        tokens: make(map[string]*Token),
        ttl:    24 * time.Hour,
    }
}

// Store saves a token with encryption.
func (s *SessionStore) Store(userID string, token *Token) error {
    encrypted, err := encryptAES(token.Value)
    if err != nil {
        return err
    }
    token.Value = encrypted
    s.tokens[userID] = token
    return nil
}"""

AUTH_GO_PARTIAL = """\
package auth

import "time"

// SessionStore manages authentication tokens.
type SessionStore struct {
    tokens map[string]*Token
    ttl    time.Duration
}

// NewSessionStore creates a new session store with a 24h TTL.
func NewSessionStore() *SessionStore {
    return &SessionStore{
        tokens: make(map[string]*Token),
        ttl:    24 * time.Hour,
    }
}"""

AUTH_GO_EDITED = """\
package auth

import "time"

// SessionStore manages authentication tokens.
type SessionStore struct {
    tokens map[string]*Token
    ttl    time.Duration
}

// NewSessionStore creates a new session store with a 48h TTL.
func NewSessionStore() *SessionStore {
    return &SessionStore{
        tokens: make(map[string]*Token),
        ttl:    48 * time.Hour,
    }
}"""

API_GO = """\
package api

import "net/http"

// Router sets up the HTTP routes.
func Router() *http.ServeMux {
    mux := http.NewServeMux()
    mux.HandleFunc("/health", healthHandler)
    mux.HandleFunc("/api/v1/users", usersHandler)
    return mux
}

func healthHandler(w http.ResponseWriter, r *http.Request) {
    w.WriteHeader(http.StatusOK)
}"""

UTIL_PY = """\
\"\"\"Utility module for common operations.\"\"\"


def normalize_path(path: str) -> str:
    \"\"\"Normalize a file path for consistent comparison.\"\"\"
    return path.replace("\\\\", "/").strip("/")


def format_range(start: int, end: int) -> str:
    \"\"\"Format a line range as 'start-end'.\"\"\"
    return f"{start}-{end}\""""

UNICODE_CODE = """\
package main

// Berechne den Hash-Wert fur den gegebenen Inhalt.
func berechneHash(inhalt string) string {
    // Ruckgabewert ist ein SHA-256 Hash
    return sha256Hex(inhalt)
}"""
