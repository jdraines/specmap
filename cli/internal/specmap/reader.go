package specmap

import (
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"strings"
)

// SpecmapFile is the top-level structure of a .specmap/{branch}.json file.
type SpecmapFile struct {
	Version       int                        `json:"version"`
	Branch        string                     `json:"branch"`
	BaseBranch    string                     `json:"base_branch"`
	UpdatedAt     string                     `json:"updated_at"`
	UpdatedBy     string                     `json:"updated_by"`
	SpecDocuments map[string]SpecDocument     `json:"spec_documents"`
	Mappings      []Mapping                  `json:"mappings"`
	IgnorePatterns []string                  `json:"ignore_patterns"`
}

// SpecDocument represents a tracked spec file.
type SpecDocument struct {
	DocHash  string                 `json:"doc_hash"`
	Sections map[string]SpecSection `json:"sections"`
}

// SpecSection represents a section within a spec document.
type SpecSection struct {
	HeadingPath []string `json:"heading_path"`
	HeadingLine int      `json:"heading_line"`
	SectionHash string   `json:"section_hash"`
}

// Mapping links a spec span to a code target.
type Mapping struct {
	ID        string     `json:"id"`
	SpecSpans []SpecSpan `json:"spec_spans"`
	CodeTarget CodeTarget `json:"code_target"`
	Stale     bool       `json:"stale"`
	CreatedAt string     `json:"created_at"`
}

// SpecSpan is a range within a spec document.
type SpecSpan struct {
	SpecFile    string   `json:"spec_file"`
	HeadingPath []string `json:"heading_path"`
	SpanOffset  int      `json:"span_offset"`
	SpanLength  int      `json:"span_length"`
	SpanHash    string   `json:"span_hash"`
	Relevance   float64  `json:"relevance"`
}

// CodeTarget is a range within a source file.
type CodeTarget struct {
	File        string `json:"file"`
	StartLine   int    `json:"start_line"`
	EndLine     int    `json:"end_line"`
	ContentHash string `json:"content_hash"`
}

// SanitizeBranch converts a branch name to a filename-safe form.
// Slashes are replaced with "--".
func SanitizeBranch(branch string) string {
	return strings.ReplaceAll(branch, "/", "--")
}

// SpecmapFilePath returns the path to the specmap JSON file for the given branch.
func SpecmapFilePath(repoRoot, branch string) string {
	filename := SanitizeBranch(branch) + ".json"
	return filepath.Join(repoRoot, ".specmap", filename)
}

// Load reads and parses .specmap/{branch}.json from the given repo root.
func Load(repoRoot, branch string) (*SpecmapFile, error) {
	fpath := SpecmapFilePath(repoRoot, branch)

	data, err := os.ReadFile(fpath)
	if err != nil {
		return nil, fmt.Errorf("reading specmap file %s: %w", fpath, err)
	}

	var sf SpecmapFile
	if err := json.Unmarshal(data, &sf); err != nil {
		return nil, fmt.Errorf("parsing specmap file %s: %w", fpath, err)
	}

	// Basic schema validation.
	if sf.Version == 0 {
		return nil, fmt.Errorf("specmap file %s: missing or zero 'version' field", fpath)
	}
	if sf.Branch == "" {
		return nil, fmt.Errorf("specmap file %s: missing 'branch' field", fpath)
	}

	return &sf, nil
}
