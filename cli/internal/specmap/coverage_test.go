package specmap

import (
	"math"
	"testing"

	"github.com/specmap/specmap/cli/internal/git"
)

func TestCalculateCoverageFullCoverage(t *testing.T) {
	sf := &SpecmapFile{
		Branch:     "feature/test",
		BaseBranch: "main",
		Mappings: []Mapping{
			{
				CodeTarget: CodeTarget{
					File:      "src/main.go",
					StartLine: 1,
					EndLine:   10,
				},
			},
			{
				CodeTarget: CodeTarget{
					File:      "src/util.go",
					StartLine: 5,
					EndLine:   20,
				},
			},
		},
	}

	changedFiles := map[string][]git.LineRange{
		"src/main.go": {{Start: 1, End: 10}},
		"src/util.go": {{Start: 5, End: 20}},
	}

	report := CalculateCoverage(sf, changedFiles, "/repo")

	if report.Coverage != 1.0 {
		t.Errorf("Coverage = %f, want 1.0", report.Coverage)
	}
	if report.TotalFiles != 2 {
		t.Errorf("TotalFiles = %d, want 2", report.TotalFiles)
	}
	if report.MappedFiles != 2 {
		t.Errorf("MappedFiles = %d, want 2", report.MappedFiles)
	}
	if report.TotalLines != 26 { // 10 + 16
		t.Errorf("TotalLines = %d, want 26", report.TotalLines)
	}
	if report.MappedLines != 26 {
		t.Errorf("MappedLines = %d, want 26", report.MappedLines)
	}
	if len(report.Unmapped) != 0 {
		t.Errorf("Unmapped count = %d, want 0", len(report.Unmapped))
	}
}

func TestCalculateCoveragePartialCoverage(t *testing.T) {
	sf := &SpecmapFile{
		Branch:     "feature/test",
		BaseBranch: "main",
		Mappings: []Mapping{
			{
				CodeTarget: CodeTarget{
					File:      "src/main.go",
					StartLine: 1,
					EndLine:   10,
				},
			},
		},
	}

	changedFiles := map[string][]git.LineRange{
		"src/main.go":  {{Start: 1, End: 10}},  // Covered.
		"src/other.go": {{Start: 1, End: 10}},   // Not covered.
	}

	report := CalculateCoverage(sf, changedFiles, "/repo")

	if report.Coverage != 0.5 {
		t.Errorf("Coverage = %f, want 0.5", report.Coverage)
	}
	if report.MappedFiles != 1 {
		t.Errorf("MappedFiles = %d, want 1", report.MappedFiles)
	}
	if report.TotalFiles != 2 {
		t.Errorf("TotalFiles = %d, want 2", report.TotalFiles)
	}
	if len(report.Unmapped) != 1 {
		t.Errorf("Unmapped count = %d, want 1", len(report.Unmapped))
	}
	if len(report.Unmapped) == 1 && report.Unmapped[0].File != "src/other.go" {
		t.Errorf("Unmapped[0].File = %q, want 'src/other.go'", report.Unmapped[0].File)
	}
}

func TestCalculateCoverageNoCoverage(t *testing.T) {
	sf := &SpecmapFile{
		Branch:     "feature/test",
		BaseBranch: "main",
		Mappings:   []Mapping{},
	}

	changedFiles := map[string][]git.LineRange{
		"src/main.go": {{Start: 1, End: 50}},
	}

	report := CalculateCoverage(sf, changedFiles, "/repo")

	if report.Coverage != 0.0 {
		t.Errorf("Coverage = %f, want 0.0", report.Coverage)
	}
	if report.MappedLines != 0 {
		t.Errorf("MappedLines = %d, want 0", report.MappedLines)
	}
}

func TestCalculateCoverageNoChanges(t *testing.T) {
	sf := &SpecmapFile{
		Branch:     "feature/test",
		BaseBranch: "main",
	}

	changedFiles := map[string][]git.LineRange{}

	report := CalculateCoverage(sf, changedFiles, "/repo")

	// No changes means nothing to cover, so coverage is 1.0.
	if report.Coverage != 1.0 {
		t.Errorf("Coverage = %f, want 1.0", report.Coverage)
	}
}

func TestCalculateCoverageNilSpecmapFile(t *testing.T) {
	changedFiles := map[string][]git.LineRange{
		"src/main.go": {{Start: 1, End: 20}},
	}

	report := CalculateCoverage(nil, changedFiles, "/repo")

	if report.Coverage != 0.0 {
		t.Errorf("Coverage = %f, want 0.0", report.Coverage)
	}
	if report.TotalLines != 20 {
		t.Errorf("TotalLines = %d, want 20", report.TotalLines)
	}
	if report.MappedLines != 0 {
		t.Errorf("MappedLines = %d, want 0", report.MappedLines)
	}
}

func TestCalculateCoverageStaleMappings(t *testing.T) {
	sf := &SpecmapFile{
		Branch:     "feature/test",
		BaseBranch: "main",
		Mappings: []Mapping{
			{
				CodeTarget: CodeTarget{
					File:      "src/main.go",
					StartLine: 1,
					EndLine:   10,
				},
				Stale: true,
			},
		},
	}

	changedFiles := map[string][]git.LineRange{
		"src/main.go": {{Start: 1, End: 10}},
	}

	report := CalculateCoverage(sf, changedFiles, "/repo")

	if len(report.Stale) != 1 {
		t.Errorf("Stale count = %d, want 1", len(report.Stale))
	}
	if len(report.Stale) == 1 {
		if report.Stale[0].File != "src/main.go" {
			t.Errorf("Stale[0].File = %q, want 'src/main.go'", report.Stale[0].File)
		}
		if report.Stale[0].Reason != "marked stale" {
			t.Errorf("Stale[0].Reason = %q, want 'marked stale'", report.Stale[0].Reason)
		}
	}
}

func TestCalculateCoveragePartialLineOverlap(t *testing.T) {
	sf := &SpecmapFile{
		Branch:     "feature/test",
		BaseBranch: "main",
		Mappings: []Mapping{
			{
				CodeTarget: CodeTarget{
					File:      "src/main.go",
					StartLine: 5,
					EndLine:   15,
				},
			},
		},
	}

	// Changed lines 1-20, but only 5-15 are mapped.
	changedFiles := map[string][]git.LineRange{
		"src/main.go": {{Start: 1, End: 20}},
	}

	report := CalculateCoverage(sf, changedFiles, "/repo")

	// 11 out of 20 lines covered.
	expectedCoverage := 11.0 / 20.0
	if math.Abs(report.Coverage-expectedCoverage) > 0.001 {
		t.Errorf("Coverage = %f, want %f", report.Coverage, expectedCoverage)
	}
	if report.MappedLines != 11 {
		t.Errorf("MappedLines = %d, want 11", report.MappedLines)
	}
}
