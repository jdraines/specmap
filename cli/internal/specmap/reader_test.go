package specmap

import (
	"encoding/json"
	"os"
	"path/filepath"
	"testing"
)

func TestSanitizeBranch(t *testing.T) {
	tests := []struct {
		input string
		want  string
	}{
		{"main", "main"},
		{"feature/auth", "feature--auth"},
		{"feature/add-auth", "feature--add-auth"},
		{"release/v1.0/hotfix", "release--v1.0--hotfix"},
		{"no-slashes", "no-slashes"},
		{"a/b/c/d", "a--b--c--d"},
	}

	for _, tt := range tests {
		t.Run(tt.input, func(t *testing.T) {
			got := SanitizeBranch(tt.input)
			if got != tt.want {
				t.Errorf("SanitizeBranch(%q) = %q, want %q", tt.input, got, tt.want)
			}
		})
	}
}

func TestLoad(t *testing.T) {
	// Create a temporary directory with a .specmap/ folder and sample JSON.
	tmpDir := t.TempDir()
	specmapDir := filepath.Join(tmpDir, ".specmap")
	if err := os.MkdirAll(specmapDir, 0755); err != nil {
		t.Fatal(err)
	}

	sf := SpecmapFile{
		Version:    1,
		Branch:     "feature/test",
		BaseBranch: "main",
		UpdatedAt:  "2026-03-19T14:30:00Z",
		UpdatedBy:  "test",
		SpecDocuments: map[string]SpecDocument{
			"docs/spec.md": {
				DocHash: "sha256:abc123",
				Sections: map[string]SpecSection{
					"Intro": {
						HeadingPath: []string{"Intro"},
						HeadingLine: 1,
						SectionHash: "sha256:def456",
					},
				},
			},
		},
		Mappings: []Mapping{
			{
				ID: "m_001",
				SpecSpans: []SpecSpan{
					{
						SpecFile:    "docs/spec.md",
						HeadingPath: []string{"Intro"},
						SpanOffset:  0,
						SpanLength:  10,
						SpanHash:    "sha256:aaa111",
						Relevance:   1.0,
					},
				},
				CodeTarget: CodeTarget{
					File:        "src/main.go",
					StartLine:   1,
					EndLine:     10,
					ContentHash: "sha256:bbb222",
				},
				Stale:     false,
				CreatedAt: "2026-03-19T14:25:00Z",
			},
		},
		IgnorePatterns: []string{"*.generated.go"},
	}

	data, err := json.MarshalIndent(sf, "", "  ")
	if err != nil {
		t.Fatal(err)
	}

	filename := SanitizeBranch("feature/test") + ".json"
	if err := os.WriteFile(filepath.Join(specmapDir, filename), data, 0644); err != nil {
		t.Fatal(err)
	}

	// Test successful load.
	loaded, err := Load(tmpDir, "feature/test")
	if err != nil {
		t.Fatalf("Load() error: %v", err)
	}

	if loaded.Version != 1 {
		t.Errorf("Version = %d, want 1", loaded.Version)
	}
	if loaded.Branch != "feature/test" {
		t.Errorf("Branch = %q, want %q", loaded.Branch, "feature/test")
	}
	if loaded.BaseBranch != "main" {
		t.Errorf("BaseBranch = %q, want %q", loaded.BaseBranch, "main")
	}
	if len(loaded.SpecDocuments) != 1 {
		t.Errorf("SpecDocuments count = %d, want 1", len(loaded.SpecDocuments))
	}
	if len(loaded.Mappings) != 1 {
		t.Errorf("Mappings count = %d, want 1", len(loaded.Mappings))
	}
	if loaded.Mappings[0].CodeTarget.StartLine != 1 {
		t.Errorf("StartLine = %d, want 1", loaded.Mappings[0].CodeTarget.StartLine)
	}
}

func TestLoadMissingFile(t *testing.T) {
	tmpDir := t.TempDir()
	_, err := Load(tmpDir, "nonexistent")
	if err == nil {
		t.Error("Load() expected error for missing file, got nil")
	}
}

func TestLoadInvalidJSON(t *testing.T) {
	tmpDir := t.TempDir()
	specmapDir := filepath.Join(tmpDir, ".specmap")
	if err := os.MkdirAll(specmapDir, 0755); err != nil {
		t.Fatal(err)
	}

	// Write invalid JSON.
	if err := os.WriteFile(filepath.Join(specmapDir, "bad.json"), []byte("{invalid"), 0644); err != nil {
		t.Fatal(err)
	}

	_, err := Load(tmpDir, "bad")
	if err == nil {
		t.Error("Load() expected error for invalid JSON, got nil")
	}
}

func TestLoadMissingVersion(t *testing.T) {
	tmpDir := t.TempDir()
	specmapDir := filepath.Join(tmpDir, ".specmap")
	if err := os.MkdirAll(specmapDir, 0755); err != nil {
		t.Fatal(err)
	}

	// JSON with version=0 (Go zero value, meaning field is absent or zero).
	data := `{"branch": "test", "base_branch": "main"}`
	if err := os.WriteFile(filepath.Join(specmapDir, "test.json"), []byte(data), 0644); err != nil {
		t.Fatal(err)
	}

	_, err := Load(tmpDir, "test")
	if err == nil {
		t.Error("Load() expected error for missing version, got nil")
	}
}

func TestLoadMissingBranch(t *testing.T) {
	tmpDir := t.TempDir()
	specmapDir := filepath.Join(tmpDir, ".specmap")
	if err := os.MkdirAll(specmapDir, 0755); err != nil {
		t.Fatal(err)
	}

	data := `{"version": 1, "base_branch": "main"}`
	if err := os.WriteFile(filepath.Join(specmapDir, "test.json"), []byte(data), 0644); err != nil {
		t.Fatal(err)
	}

	_, err := Load(tmpDir, "test")
	if err == nil {
		t.Error("Load() expected error for missing branch, got nil")
	}
}

func TestSpecmapFilePath(t *testing.T) {
	got := SpecmapFilePath("/repo", "feature/auth")
	want := filepath.Join("/repo", ".specmap", "feature--auth.json")
	if got != want {
		t.Errorf("SpecmapFilePath = %q, want %q", got, want)
	}
}
