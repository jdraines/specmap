package cmd

import (
	"encoding/json"
	"fmt"
	"os"
	"sort"

	"github.com/spf13/cobra"

	"github.com/specmap/specmap/cli/internal/git"
	"github.com/specmap/specmap/cli/internal/specmap"
)

var (
	threshold float64
	baseBranch string
	jsonOutput bool
)

var checkCmd = &cobra.Command{
	Use:   "check",
	Short: "Check coverage and enforce thresholds (CI mode)",
	Long:  "Calculates mapping coverage for changed files and enforces a minimum coverage threshold.",
	RunE:  runCheck,
}

func init() {
	checkCmd.Flags().Float64Var(&threshold, "threshold", 0.0, "minimum coverage ratio (0.0-1.0)")
	checkCmd.Flags().StringVar(&baseBranch, "base", "", "base branch for diff (default: from specmap file)")
	checkCmd.Flags().BoolVar(&jsonOutput, "json", false, "output JSON instead of human-readable")
	rootCmd.AddCommand(checkCmd)
}

// checkJSONOutput is the JSON structure for check output.
type checkJSONOutput struct {
	Branch      string              `json:"branch"`
	BaseBranch  string              `json:"base_branch"`
	TotalFiles  int                 `json:"total_files"`
	MappedFiles int                 `json:"mapped_files"`
	TotalLines  int                 `json:"total_lines"`
	MappedLines int                 `json:"mapped_lines"`
	Coverage    float64             `json:"coverage"`
	Threshold   float64             `json:"threshold"`
	Pass        bool                `json:"pass"`
	Unmapped    []specmap.UnmappedFile `json:"unmapped"`
	Stale       []specmap.StaleMapping `json:"stale"`
}

func runCheck(cmd *cobra.Command, args []string) error {
	root, err := resolveRepoRoot()
	if err != nil {
		return err
	}

	branchName, err := resolveBranch(root)
	if err != nil {
		return err
	}

	// Load specmap file (may not exist).
	sf, loadErr := specmap.Load(root, branchName)

	// Determine base branch.
	base := baseBranch
	if base == "" && sf != nil {
		base = sf.BaseBranch
	}
	if base == "" {
		base = "main"
	}

	// Get changed files.
	changedFiles, err := git.ChangedFiles(root, base)
	if err != nil {
		// If git diff fails, we still want to report what we can.
		if !jsonOutput {
			fmt.Fprintf(os.Stderr, "specmap: warning: git diff failed: %v\n", err)
		}
		changedFiles = make(map[string][]git.LineRange)
	}

	// Handle case where specmap file doesn't exist.
	if loadErr != nil {
		sf = nil
	}

	report := specmap.CalculateCoverage(sf, changedFiles, root)
	pass := report.Coverage >= threshold

	if jsonOutput {
		return outputCheckJSON(report, pass)
	}

	return outputCheckHuman(report, branchName, base, pass)
}

func outputCheckJSON(report *specmap.CoverageReport, pass bool) error {
	out := checkJSONOutput{
		Branch:      report.Branch,
		BaseBranch:  report.BaseBranch,
		TotalFiles:  report.TotalFiles,
		MappedFiles: report.MappedFiles,
		TotalLines:  report.TotalLines,
		MappedLines: report.MappedLines,
		Coverage:    report.Coverage,
		Threshold:   threshold,
		Pass:        pass,
		Unmapped:    report.Unmapped,
		Stale:       report.Stale,
	}

	// Ensure slices are not null in JSON.
	if out.Unmapped == nil {
		out.Unmapped = []specmap.UnmappedFile{}
	}
	if out.Stale == nil {
		out.Stale = []specmap.StaleMapping{}
	}

	enc := json.NewEncoder(os.Stdout)
	enc.SetIndent("", "  ")
	if err := enc.Encode(out); err != nil {
		return fmt.Errorf("encoding JSON: %w", err)
	}

	if !pass {
		os.Exit(1)
	}
	return nil
}

func outputCheckHuman(report *specmap.CoverageReport, branchName, base string, pass bool) error {
	fmt.Printf("specmap: checking coverage for %s (base: %s)\n", branchName, base)
	fmt.Printf("Files: %d/%d mapped | Lines: %d/%d mapped\n",
		report.MappedFiles, report.TotalFiles,
		report.MappedLines, report.TotalLines)

	// Show unmapped files, sorted by coverage ascending.
	if len(report.Unmapped) > 0 {
		sorted := make([]specmap.UnmappedFile, len(report.Unmapped))
		copy(sorted, report.Unmapped)
		sort.Slice(sorted, func(i, j int) bool {
			return sorted[i].Coverage < sorted[j].Coverage
		})

		parts := make([]string, 0, len(sorted))
		for _, u := range sorted {
			parts = append(parts, fmt.Sprintf("%s (%.0f%%, %d lines)",
				u.File, u.Coverage*100, u.TotalLines-u.MappedLines))
		}
		fmt.Printf("Unmapped: %s\n", joinComma(parts))
	}

	// Show stale mappings.
	if len(report.Stale) > 0 {
		parts := make([]string, 0, len(report.Stale))
		for _, s := range report.Stale {
			parts = append(parts, fmt.Sprintf("%s:%d-%d (%s)",
				s.File, s.StartLine, s.EndLine, s.Reason))
		}
		fmt.Printf("Stale: %s\n", joinComma(parts))
	}

	coveragePct := report.Coverage * 100
	thresholdPct := threshold * 100
	result := green("PASS")
	if !pass {
		result = red("FAIL")
	}
	fmt.Printf("Overall: %.1f%% (threshold: %.1f%%) \u2014 %s\n", coveragePct, thresholdPct, result)

	if !pass {
		os.Exit(1)
	}
	return nil
}

func joinComma(parts []string) string {
	result := ""
	for i, p := range parts {
		if i > 0 {
			result += ", "
		}
		result += p
	}
	return result
}
