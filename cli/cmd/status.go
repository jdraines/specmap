package cmd

import (
	"fmt"
	"os"

	"github.com/spf13/cobra"

	"github.com/specmap/specmap/cli/internal/specmap"
)

var statusCmd = &cobra.Command{
	Use:   "status",
	Short: "Show human-readable mapping summary",
	Long:  "Displays spec documents, mapping counts, and stale mappings for the current branch.",
	RunE:  runStatus,
}

func init() {
	rootCmd.AddCommand(statusCmd)
}

func runStatus(cmd *cobra.Command, args []string) error {
	root, err := resolveRepoRoot()
	if err != nil {
		return err
	}

	branchName, err := resolveBranch(root)
	if err != nil {
		return err
	}

	sf, err := specmap.Load(root, branchName)
	if err != nil {
		fmt.Fprintf(os.Stderr, "specmap: no specmap file found for branch %s\n", branchName)
		return err
	}

	fmt.Printf("specmap: status for %s (base: %s)\n\n", sf.Branch, sf.BaseBranch)

	// Spec Documents summary.
	fmt.Println("Spec Documents:")
	for docPath, doc := range sf.SpecDocuments {
		sectionCount := len(doc.Sections)
		// Count mappings that reference this doc.
		mappingCount := 0
		for _, m := range sf.Mappings {
			for _, span := range m.SpecSpans {
				if span.SpecFile == docPath {
					mappingCount++
					break
				}
			}
		}
		fmt.Printf("  %s (%d sections, %d mappings)\n", docPath, sectionCount, mappingCount)
	}

	// Overall mapping stats.
	totalMappings := len(sf.Mappings)
	staleMappings := 0
	type staleInfo struct {
		file      string
		startLine int
		endLine   int
		specFile  string
		heading   string
	}
	var staleDetails []staleInfo

	for _, m := range sf.Mappings {
		if m.Stale {
			staleMappings++
			heading := ""
			specFile := ""
			if len(m.SpecSpans) > 0 {
				specFile = m.SpecSpans[0].SpecFile
				heading = joinHeadingPath(m.SpecSpans[0].HeadingPath)
			}
			staleDetails = append(staleDetails, staleInfo{
				file:      m.CodeTarget.File,
				startLine: m.CodeTarget.StartLine,
				endLine:   m.CodeTarget.EndLine,
				specFile:  specFile,
				heading:   heading,
			})
		}
	}

	validMappings := totalMappings - staleMappings
	fmt.Printf("\nMappings: %d total (%d valid, %d stale)\n", totalMappings, validMappings, staleMappings)

	if len(staleDetails) > 0 {
		fmt.Println("Stale:")
		for _, s := range staleDetails {
			target := fmt.Sprintf("%s:%d-%d", s.file, s.startLine, s.endLine)
			spec := s.specFile
			if s.heading != "" {
				spec += " > " + s.heading
			}
			fmt.Printf("  %s \u2192 %s\n", target, spec)
		}
	}

	fmt.Printf("\nCoverage: see 'specmap check' for coverage details\n")

	return nil
}
