package cmd

import (
	"fmt"
	"os"

	"github.com/spf13/cobra"

	"github.com/specmap/specmap/cli/internal/specmap"
)

var validateCmd = &cobra.Command{
	Use:   "validate",
	Short: "Validate specmap file schema and hash integrity",
	Long:  "Validates the .specmap/{branch}.json file: checks JSON structure, verifies doc hashes, code target hashes, and spec span hashes.",
	RunE:  runValidate,
}

func init() {
	rootCmd.AddCommand(validateCmd)
}

func runValidate(cmd *cobra.Command, args []string) error {
	root, err := resolveRepoRoot()
	if err != nil {
		return err
	}

	branchName, err := resolveBranch(root)
	if err != nil {
		return err
	}

	sanitized := specmap.SanitizeBranch(branchName)
	fmt.Printf("specmap: validating .specmap/%s.json\n", sanitized)

	sf, err := specmap.Load(root, branchName)
	if err != nil {
		fmt.Printf("%s Schema invalid: %v\n", crossMark(), err)
		os.Exit(1)
		return nil
	}

	fmt.Printf("%s Schema valid (version %d)\n", checkMark(), sf.Version)

	results, err := specmap.Validate(sf, root)
	if err != nil {
		return fmt.Errorf("validation error: %w", err)
	}

	valid := 0
	invalid := 0
	total := len(results)

	for _, r := range results {
		indicator := checkMark()
		if !r.Valid {
			indicator = crossMark()
			invalid++
		} else {
			valid++
		}

		label := "Spec"
		loc := r.File
		if r.Lines != "" {
			label = "Code"
			loc = fmt.Sprintf("%s:%s", r.File, r.Lines)
		}

		fmt.Printf("%s %s: %s (%s)\n", indicator, label, loc, r.Message)
	}

	// Summary.
	if invalid == 0 {
		fmt.Printf("%s %d/%d mappings valid\n", checkMark(), valid, total)
	} else {
		fmt.Printf("%s %d/%d mappings valid, %d hash mismatch\n", crossMark(), valid, total, invalid)
		os.Exit(1)
	}

	return nil
}
