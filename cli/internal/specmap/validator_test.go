package specmap

import (
	"os"
	"path/filepath"
	"strings"
	"testing"
)

func TestHashContent(t *testing.T) {
	hash := HashContent("hello world")

	// Must start with "sha256:".
	if !strings.HasPrefix(hash, "sha256:") {
		t.Errorf("HashContent() = %q, want prefix 'sha256:'", hash)
	}

	// The hex part must be exactly 16 characters.
	hexPart := strings.TrimPrefix(hash, "sha256:")
	if len(hexPart) != 16 {
		t.Errorf("HashContent() hex part length = %d, want 16", len(hexPart))
	}

	// Verify consistency: same input produces same output.
	hash2 := HashContent("hello world")
	if hash != hash2 {
		t.Errorf("HashContent() not consistent: %q != %q", hash, hash2)
	}

	// Different input produces different output.
	hash3 := HashContent("hello world!")
	if hash == hash3 {
		t.Errorf("HashContent() collision: %q == %q for different inputs", hash, hash3)
	}
}

func TestHashBytes(t *testing.T) {
	hash := HashBytes([]byte("hello world"))
	hashFromContent := HashContent("hello world")
	if hash != hashFromContent {
		t.Errorf("HashBytes and HashContent disagree: %q != %q", hash, hashFromContent)
	}
}

func TestValidateValidHashes(t *testing.T) {
	tmpDir := t.TempDir()

	// Create spec file.
	specContent := "# Introduction\n\nThis is the spec for authentication.\n"
	specDir := filepath.Join(tmpDir, "docs")
	os.MkdirAll(specDir, 0755)
	os.WriteFile(filepath.Join(specDir, "spec.md"), []byte(specContent), 0644)

	// Create code file.
	codeContent := "package main\n\nfunc hello() {\n\tfmt.Println(\"hello\")\n}\n"
	srcDir := filepath.Join(tmpDir, "src")
	os.MkdirAll(srcDir, 0755)
	os.WriteFile(filepath.Join(srcDir, "main.go"), []byte(codeContent), 0644)

	// Compute correct hashes.
	docHash := HashBytes([]byte(specContent))
	// Lines 1-3 of the code file.
	codeLines := strings.Split(codeContent, "\n")
	codePart := strings.Join(codeLines[0:3], "\n")
	codeHash := HashContent(codePart)
	// Spec span: offset 0, length 16 = "# Introduction\n"
	spanText := specContent[0:16]
	spanHash := HashContent(spanText)

	sf := &SpecmapFile{
		Version:    1,
		Branch:     "test",
		BaseBranch: "main",
		SpecDocuments: map[string]SpecDocument{
			"docs/spec.md": {
				DocHash: docHash,
			},
		},
		Mappings: []Mapping{
			{
				ID: "m_001",
				SpecSpans: []SpecSpan{
					{
						SpecFile:   "docs/spec.md",
						SpanOffset: 0,
						SpanLength: 16,
						SpanHash:   spanHash,
					},
				},
				CodeTarget: CodeTarget{
					File:        "src/main.go",
					StartLine:   1,
					EndLine:     3,
					ContentHash: codeHash,
				},
			},
		},
	}

	results, err := Validate(sf, tmpDir)
	if err != nil {
		t.Fatalf("Validate() error: %v", err)
	}

	for _, r := range results {
		if !r.Valid {
			t.Errorf("expected valid result for %s, got invalid: %s", r.File, r.Message)
		}
	}
}

func TestValidateInvalidDocHash(t *testing.T) {
	tmpDir := t.TempDir()

	specDir := filepath.Join(tmpDir, "docs")
	os.MkdirAll(specDir, 0755)
	os.WriteFile(filepath.Join(specDir, "spec.md"), []byte("some content"), 0644)

	sf := &SpecmapFile{
		Version:    1,
		Branch:     "test",
		BaseBranch: "main",
		SpecDocuments: map[string]SpecDocument{
			"docs/spec.md": {
				DocHash: "sha256:0000000000000000", // Wrong hash.
			},
		},
		Mappings: []Mapping{},
	}

	results, err := Validate(sf, tmpDir)
	if err != nil {
		t.Fatalf("Validate() error: %v", err)
	}

	found := false
	for _, r := range results {
		if r.File == "docs/spec.md" && !r.Valid {
			found = true
			if !strings.Contains(r.Message, "hash mismatch") {
				t.Errorf("expected 'hash mismatch' message, got %q", r.Message)
			}
		}
	}
	if !found {
		t.Error("expected invalid result for docs/spec.md with wrong hash")
	}
}

func TestValidateInvalidCodeHash(t *testing.T) {
	tmpDir := t.TempDir()

	srcDir := filepath.Join(tmpDir, "src")
	os.MkdirAll(srcDir, 0755)
	os.WriteFile(filepath.Join(srcDir, "main.go"), []byte("line1\nline2\nline3\n"), 0644)

	sf := &SpecmapFile{
		Version:    1,
		Branch:     "test",
		BaseBranch: "main",
		SpecDocuments: map[string]SpecDocument{},
		Mappings: []Mapping{
			{
				ID:        "m_001",
				SpecSpans: []SpecSpan{},
				CodeTarget: CodeTarget{
					File:        "src/main.go",
					StartLine:   1,
					EndLine:     2,
					ContentHash: "sha256:0000000000000000", // Wrong hash.
				},
			},
		},
	}

	results, err := Validate(sf, tmpDir)
	if err != nil {
		t.Fatalf("Validate() error: %v", err)
	}

	found := false
	for _, r := range results {
		if r.File == "src/main.go" && !r.Valid {
			found = true
			if !strings.Contains(r.Message, "hash mismatch") {
				t.Errorf("expected 'hash mismatch' message, got %q", r.Message)
			}
		}
	}
	if !found {
		t.Error("expected invalid result for src/main.go with wrong hash")
	}
}

func TestValidateMissingFile(t *testing.T) {
	tmpDir := t.TempDir()

	sf := &SpecmapFile{
		Version:    1,
		Branch:     "test",
		BaseBranch: "main",
		SpecDocuments: map[string]SpecDocument{
			"nonexistent.md": {
				DocHash: "sha256:0000000000000000",
			},
		},
		Mappings: []Mapping{},
	}

	results, err := Validate(sf, tmpDir)
	if err != nil {
		t.Fatalf("Validate() error: %v", err)
	}

	found := false
	for _, r := range results {
		if r.File == "nonexistent.md" && !r.Valid {
			found = true
			if !strings.Contains(r.Message, "cannot read") {
				t.Errorf("expected 'cannot read' message, got %q", r.Message)
			}
		}
	}
	if !found {
		t.Error("expected invalid result for missing file")
	}
}

func TestValidateLineRangeOutOfBounds(t *testing.T) {
	tmpDir := t.TempDir()

	srcDir := filepath.Join(tmpDir, "src")
	os.MkdirAll(srcDir, 0755)
	os.WriteFile(filepath.Join(srcDir, "small.go"), []byte("line1\nline2\n"), 0644)

	sf := &SpecmapFile{
		Version:       1,
		Branch:        "test",
		BaseBranch:    "main",
		SpecDocuments: map[string]SpecDocument{},
		Mappings: []Mapping{
			{
				ID:        "m_001",
				SpecSpans: []SpecSpan{},
				CodeTarget: CodeTarget{
					File:        "src/small.go",
					StartLine:   1,
					EndLine:     100, // Out of bounds.
					ContentHash: "sha256:0000000000000000",
				},
			},
		},
	}

	results, err := Validate(sf, tmpDir)
	if err != nil {
		t.Fatalf("Validate() error: %v", err)
	}

	found := false
	for _, r := range results {
		if r.File == "src/small.go" && !r.Valid {
			found = true
			if !strings.Contains(r.Message, "out of bounds") {
				t.Errorf("expected 'out of bounds' message, got %q", r.Message)
			}
		}
	}
	if !found {
		t.Error("expected invalid result for out of bounds line range")
	}
}
