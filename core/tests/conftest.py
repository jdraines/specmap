"""Common test fixtures for specmap-mcp tests."""

from __future__ import annotations

import subprocess
from datetime import datetime, timezone
from pathlib import Path

import pytest

from specmap.state.models import (
    Annotation,
    SpecmapFile,
    SpecRef,
)


SAMPLE_SPEC = """\
# Authentication

This document describes the authentication system.

## Token Storage

Tokens are stored securely in the session store. Each token has a TTL
of 24 hours and is refreshed on activity.

### Encryption

All tokens are encrypted at rest using AES-256-GCM.

## Session Management

Sessions track user activity and expire after inactivity.

### Timeout Rules

- Idle timeout: 30 minutes
- Absolute timeout: 24 hours
"""

SAMPLE_GO_FILE = """\
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
}
"""

SAMPLE_DIFF = """\
diff --git a/api/internal/auth/session.go b/api/internal/auth/session.go
new file mode 100644
index 0000000..1234567
--- /dev/null
+++ b/api/internal/auth/session.go
@@ -0,0 +1,31 @@
+package auth
+
+import (
+    "crypto/aes"
+    "time"
+)
+
+// SessionStore manages authentication tokens.
+type SessionStore struct {
+    tokens map[string]*Token
+    ttl    time.Duration
+}
+
+// NewSessionStore creates a new session store with a 24h TTL.
+func NewSessionStore() *SessionStore {
+    return &SessionStore{
+        tokens: make(map[string]*Token),
+        ttl:    24 * time.Hour,
+    }
+}
+
+// Store saves a token with encryption.
+func (s *SessionStore) Store(userID string, token *Token) error {
+    encrypted, err := encryptAES(token.Value)
+    if err != nil {
+        return err
+    }
+    token.Value = encrypted
+    s.tokens[userID] = token
+    return nil
+}
"""


@pytest.fixture
def tmp_repo(tmp_path: Path) -> Path:
    """Create a temp directory with git init, a sample spec file, and source files."""
    repo = tmp_path / "test-repo"
    repo.mkdir()

    # Initialize git
    subprocess.run(["git", "init"], cwd=str(repo), capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "test@test.com"],
        cwd=str(repo),
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test"],
        cwd=str(repo),
        capture_output=True,
    )

    # Create spec file
    docs_dir = repo / "docs"
    docs_dir.mkdir()
    (docs_dir / "auth-spec.md").write_text(SAMPLE_SPEC)

    # Create source file
    src_dir = repo / "api" / "internal" / "auth"
    src_dir.mkdir(parents=True)
    (src_dir / "session.go").write_text(SAMPLE_GO_FILE)

    # Create .specmap directory
    specmap_dir = repo / ".specmap"
    specmap_dir.mkdir()

    # Initial commit
    subprocess.run(["git", "add", "."], cwd=str(repo), capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "Initial commit"],
        cwd=str(repo),
        capture_output=True,
    )

    return repo


@pytest.fixture
def sample_specmap() -> SpecmapFile:
    """Return a SpecmapFile with sample annotation data."""
    return SpecmapFile(
        version=2,
        branch="feature/add-auth",
        base_branch="main",
        head_sha="abc123def456",
        updated_at=datetime(2026, 3, 19, 14, 30, 0, tzinfo=timezone.utc),
        updated_by="mcp:claude-code",
        annotations=[
            Annotation(
                id="a_abcdef123456",
                file="api/internal/auth/session.go",
                start_line=15,
                end_line=42,
                description=(
                    "Implements session store with 24h TTL and AES-256 "
                    "encryption at rest. [1][2]"
                ),
                refs=[
                    SpecRef(
                        id=1,
                        spec_file="docs/auth-spec.md",
                        heading="Token Storage",
                        start_line=6,
                        excerpt=(
                            "Tokens are stored securely in the session store. "
                            "Each token has a TTL of 24 hours."
                        ),
                    ),
                    SpecRef(
                        id=2,
                        spec_file="docs/auth-spec.md",
                        heading="Encryption",
                        start_line=12,
                        excerpt="All tokens are encrypted at rest using AES-256-GCM.",
                    ),
                ],
                created_at=datetime(2026, 3, 19, 14, 25, 0, tzinfo=timezone.utc),
            ),
        ],
        ignore_patterns=["*.generated.go", "*.lock", "vendor/**"],
    )


@pytest.fixture
def sample_diff() -> str:
    """Return a sample unified diff string."""
    return SAMPLE_DIFF
