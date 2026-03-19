package specmap

import (
	"fmt"

	"github.com/specmap/specmap/cli/internal/git"
)

// CoverageReport is the output of coverage calculation.
type CoverageReport struct {
	Branch      string         `json:"branch"`
	BaseBranch  string         `json:"base_branch"`
	TotalFiles  int            `json:"total_files"`
	MappedFiles int            `json:"mapped_files"`
	TotalLines  int            `json:"total_lines"`
	MappedLines int            `json:"mapped_lines"`
	Coverage    float64        `json:"coverage"`
	Unmapped    []UnmappedFile `json:"unmapped"`
	Stale       []StaleMapping `json:"stale"`
}

// UnmappedFile describes a changed file with incomplete mapping coverage.
type UnmappedFile struct {
	File        string  `json:"file"`
	Coverage    float64 `json:"coverage"`
	TotalLines  int     `json:"total_lines"`
	MappedLines int     `json:"mapped_lines"`
}

// StaleMapping describes a mapping whose hash no longer matches.
type StaleMapping struct {
	File      string `json:"file"`
	StartLine int    `json:"start_line"`
	EndLine   int    `json:"end_line"`
	Reason    string `json:"reason"`
}

// CalculateCoverage computes coverage from a specmap file and git diff results.
// changedFiles maps relative file paths to slices of changed line ranges.
// If sf is nil, it reports 0% coverage over the changed files.
func CalculateCoverage(sf *SpecmapFile, changedFiles map[string][]git.LineRange, repoRoot string) *CoverageReport {
	report := &CoverageReport{}

	if sf != nil {
		report.Branch = sf.Branch
		report.BaseBranch = sf.BaseBranch
	}

	if len(changedFiles) == 0 {
		report.Coverage = 1.0 // No changes means nothing to cover.
		return report
	}

	// Build a set of mapped line ranges per file from the specmap mappings.
	mappedRanges := make(map[string][]git.LineRange)
	if sf != nil {
		for _, m := range sf.Mappings {
			ct := m.CodeTarget
			mappedRanges[ct.File] = append(mappedRanges[ct.File], git.LineRange{
				Start: ct.StartLine,
				End:   ct.EndLine,
			})
		}
	}

	// Calculate per-file coverage.
	totalChangedLines := 0
	totalMappedLines := 0
	fileMapped := 0

	for file, ranges := range changedFiles {
		fileChangedLines := countLines(ranges)
		totalChangedLines += fileChangedLines

		fileCovered := 0
		if mapped, ok := mappedRanges[file]; ok {
			fileCovered = countOverlap(ranges, mapped)
		}
		totalMappedLines += fileCovered

		fileCoverage := 0.0
		if fileChangedLines > 0 {
			fileCoverage = float64(fileCovered) / float64(fileChangedLines)
		}

		if fileCovered > 0 {
			fileMapped++
		}

		// Report unmapped or partially mapped files.
		if fileCoverage < 1.0 {
			report.Unmapped = append(report.Unmapped, UnmappedFile{
				File:        file,
				Coverage:    fileCoverage,
				TotalLines:  fileChangedLines,
				MappedLines: fileCovered,
			})
		}
	}

	report.TotalFiles = len(changedFiles)
	report.MappedFiles = fileMapped
	report.TotalLines = totalChangedLines
	report.MappedLines = totalMappedLines

	if totalChangedLines > 0 {
		report.Coverage = float64(totalMappedLines) / float64(totalChangedLines)
	}

	// Find stale mappings.
	if sf != nil {
		for _, m := range sf.Mappings {
			if m.Stale {
				report.Stale = append(report.Stale, StaleMapping{
					File:      m.CodeTarget.File,
					StartLine: m.CodeTarget.StartLine,
					EndLine:   m.CodeTarget.EndLine,
					Reason:    "marked stale",
				})
				continue
			}
			// Check spec span hashes for staleness.
			for _, span := range m.SpecSpans {
				// We include spans whose hashes were flagged as mismatched.
				// The full hash check is done in validate; here we just note
				// mappings that are explicitly stale.
				_ = span
			}
		}
	}

	return report
}

// countLines counts the total number of individual lines in a set of ranges.
func countLines(ranges []git.LineRange) int {
	total := 0
	for _, r := range ranges {
		total += r.End - r.Start + 1
	}
	return total
}

// countOverlap counts how many lines in 'changed' are covered by 'mapped'.
func countOverlap(changed, mapped []git.LineRange) int {
	// Build a set of all changed line numbers.
	changedSet := make(map[int]bool)
	for _, r := range changed {
		for i := r.Start; i <= r.End; i++ {
			changedSet[i] = true
		}
	}

	// Count how many changed lines fall within a mapped range.
	count := 0
	for _, m := range mapped {
		for i := m.Start; i <= m.End; i++ {
			if changedSet[i] {
				count++
				delete(changedSet, i) // Don't double-count.
			}
		}
	}
	return count
}

// FormatLineRange returns a human-readable line range string.
func FormatLineRange(start, end int) string {
	return fmt.Sprintf("%d-%d", start, end)
}
