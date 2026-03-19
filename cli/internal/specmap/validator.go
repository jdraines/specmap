package specmap

import (
	"crypto/sha256"
	"encoding/hex"
	"fmt"
	"os"
	"path/filepath"
	"strings"
)

// ValidateResult holds per-item validation results.
type ValidateResult struct {
	Valid   bool
	Message string
	File    string
	Lines   string // "15-42" for code targets, empty for docs
}

// HashContent computes the specmap hash format: "sha256:" + first 16 hex chars of SHA-256.
func HashContent(content string) string {
	h := sha256.Sum256([]byte(content))
	full := hex.EncodeToString(h[:])
	return "sha256:" + full[:16]
}

// HashBytes computes the specmap hash from a byte slice.
func HashBytes(data []byte) string {
	h := sha256.Sum256(data)
	full := hex.EncodeToString(h[:])
	return "sha256:" + full[:16]
}

// Validate checks all hashes in a SpecmapFile against actual file contents.
// It verifies:
//   - doc_hash for each spec document
//   - content_hash for each code target
//   - span_hash for each spec span
func Validate(sf *SpecmapFile, repoRoot string) ([]ValidateResult, error) {
	var results []ValidateResult

	// Validate spec documents.
	for docPath, doc := range sf.SpecDocuments {
		absPath := filepath.Join(repoRoot, docPath)
		data, err := os.ReadFile(absPath)
		if err != nil {
			results = append(results, ValidateResult{
				Valid:   false,
				Message: fmt.Sprintf("cannot read file: %v", err),
				File:    docPath,
			})
			continue
		}

		actualHash := HashBytes(data)
		if actualHash == doc.DocHash {
			results = append(results, ValidateResult{
				Valid:   true,
				Message: "hash OK",
				File:    docPath,
			})
		} else {
			results = append(results, ValidateResult{
				Valid:   false,
				Message: fmt.Sprintf("hash mismatch (expected %s, got %s)", doc.DocHash, actualHash),
				File:    docPath,
			})
		}
	}

	// Validate mappings.
	for _, m := range sf.Mappings {
		ct := m.CodeTarget

		// Validate code target hash.
		absPath := filepath.Join(repoRoot, ct.File)
		data, err := os.ReadFile(absPath)
		if err != nil {
			results = append(results, ValidateResult{
				Valid:   false,
				Message: fmt.Sprintf("cannot read file: %v", err),
				File:    ct.File,
				Lines:   fmt.Sprintf("%d-%d", ct.StartLine, ct.EndLine),
			})
			continue
		}

		lines := strings.Split(string(data), "\n")
		if ct.StartLine < 1 || ct.EndLine > len(lines) || ct.StartLine > ct.EndLine {
			results = append(results, ValidateResult{
				Valid:   false,
				Message: fmt.Sprintf("line range %d-%d out of bounds (file has %d lines)", ct.StartLine, ct.EndLine, len(lines)),
				File:    ct.File,
				Lines:   fmt.Sprintf("%d-%d", ct.StartLine, ct.EndLine),
			})
			continue
		}

		// Extract the specified line range (1-indexed, inclusive).
		selectedLines := lines[ct.StartLine-1 : ct.EndLine]
		content := strings.Join(selectedLines, "\n")
		actualHash := HashContent(content)

		lineRange := fmt.Sprintf("%d-%d", ct.StartLine, ct.EndLine)
		if actualHash == ct.ContentHash {
			results = append(results, ValidateResult{
				Valid:   true,
				Message: "hash OK",
				File:    ct.File,
				Lines:   lineRange,
			})
		} else {
			results = append(results, ValidateResult{
				Valid:   false,
				Message: fmt.Sprintf("hash mismatch (expected %s, got %s)", ct.ContentHash, actualHash),
				File:    ct.File,
				Lines:   lineRange,
			})
		}

		// Validate spec span hashes.
		for _, span := range m.SpecSpans {
			specPath := filepath.Join(repoRoot, span.SpecFile)
			specData, err := os.ReadFile(specPath)
			if err != nil {
				results = append(results, ValidateResult{
					Valid:   false,
					Message: fmt.Sprintf("cannot read spec file: %v", err),
					File:    span.SpecFile,
				})
				continue
			}

			specContent := string(specData)
			if span.SpanOffset < 0 || span.SpanOffset+span.SpanLength > len(specContent) {
				results = append(results, ValidateResult{
					Valid:   false,
					Message: fmt.Sprintf("span offset %d+%d out of bounds (file length %d)", span.SpanOffset, span.SpanLength, len(specContent)),
					File:    span.SpecFile,
				})
				continue
			}

			spanText := specContent[span.SpanOffset : span.SpanOffset+span.SpanLength]
			spanActual := HashContent(spanText)
			if spanActual == span.SpanHash {
				results = append(results, ValidateResult{
					Valid:   true,
					Message: "span hash OK",
					File:    span.SpecFile,
				})
			} else {
				results = append(results, ValidateResult{
					Valid:   false,
					Message: fmt.Sprintf("span hash mismatch (expected %s, got %s)", span.SpanHash, spanActual),
					File:    span.SpecFile,
				})
			}
		}
	}

	return results, nil
}
