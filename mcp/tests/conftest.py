"""Common test fixtures for specmap-mcp tests."""

from __future__ import annotations

import subprocess
from datetime import datetime, timezone
from pathlib import Path

import pytest

from specmap_mcp.state.models import (
    CodeTarget,
    Mapping,
    SpecDocument,
    SpecmapFile,
    SpecSection,
    SpecSpan,
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
    """Return a SpecmapFile with sample data."""
    return SpecmapFile(
        version=1,
        branch="feature/add-auth",
        base_branch="main",
        updated_at=datetime(2026, 3, 19, 14, 30, 0, tzinfo=timezone.utc),
        updated_by="mcp:claude-code",
        spec_documents={
            "docs/auth-spec.md": SpecDocument(
                doc_hash="sha256:a1b2c3d4e5f60000",
                sections={
                    "Authentication > Token Storage": SpecSection(
                        heading_path=["Authentication", "Token Storage"],
                        heading_line=5,
                        section_hash="sha256:789abc0000000000",
                    ),
                    "Authentication > Token Storage > Encryption": SpecSection(
                        heading_path=["Authentication", "Token Storage", "Encryption"],
                        heading_line=10,
                        section_hash="sha256:def0120000000000",
                    ),
                },
            ),
        },
        mappings=[
            Mapping(
                id="m_abcdef123456",
                spec_spans=[
                    SpecSpan(
                        spec_file="docs/auth-spec.md",
                        heading_path=["Authentication", "Token Storage"],
                        span_offset=120,
                        span_length=100,
                        span_hash="sha256:def0120000000000",
                        relevance=1.0,
                    ),
                ],
                code_target=CodeTarget(
                    file="api/internal/auth/session.go",
                    start_line=15,
                    end_line=42,
                    content_hash="sha256:9ab0cd0000000000",
                ),
                stale=False,
                created_at=datetime(2026, 3, 19, 14, 25, 0, tzinfo=timezone.utc),
            ),
        ],
        ignore_patterns=["*.generated.go", "*.lock", "vendor/**"],
    )


@pytest.fixture
def sample_diff() -> str:
    """Return a sample unified diff string."""
    return SAMPLE_DIFF
