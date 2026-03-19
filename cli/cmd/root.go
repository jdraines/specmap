package cmd

import (
	"fmt"
	"os"
	"path/filepath"
	"strings"

	"github.com/spf13/cobra"

	"github.com/specmap/specmap/cli/internal/git"
)

var (
	repoRoot string
	branch   string
	noColor  bool
)

var rootCmd = &cobra.Command{
	Use:   "specmap",
	Short: "Spec-to-code mapping validation and coverage",
	Long:  "Specmap CLI validates .specmap/ tracking files, shows mapping status, and enforces coverage thresholds.",
}

// Execute runs the root command.
func Execute() {
	if err := rootCmd.Execute(); err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
}

func init() {
	rootCmd.PersistentFlags().StringVar(&repoRoot, "repo-root", "", "repository root (default: auto-detect)")
	rootCmd.PersistentFlags().StringVar(&branch, "branch", "", "branch name (default: auto-detect)")
	rootCmd.PersistentFlags().BoolVar(&noColor, "no-color", false, "disable color output")
}

// resolveRepoRoot finds the repository root directory.
// If --repo-root is set, it uses that value.
// Otherwise, it walks up from the current directory looking for .git/.
func resolveRepoRoot() (string, error) {
	if repoRoot != "" {
		abs, err := filepath.Abs(repoRoot)
		if err != nil {
			return "", fmt.Errorf("resolving repo root: %w", err)
		}
		return abs, nil
	}

	dir, err := os.Getwd()
	if err != nil {
		return "", fmt.Errorf("getting working directory: %w", err)
	}

	for {
		gitDir := filepath.Join(dir, ".git")
		if info, err := os.Stat(gitDir); err == nil && info.IsDir() {
			return dir, nil
		}
		parent := filepath.Dir(dir)
		if parent == dir {
			break
		}
		dir = parent
	}

	return "", fmt.Errorf("not in a git repository (no .git/ found walking up from %s)", dir)
}

// resolveBranch determines the current branch name.
// If --branch is set, it uses that value.
// Otherwise, it reads from git.
func resolveBranch(root string) (string, error) {
	if branch != "" {
		return branch, nil
	}
	return git.CurrentBranch(root)
}

// Color helpers

const (
	colorReset  = "\033[0m"
	colorGreen  = "\033[32m"
	colorRed    = "\033[31m"
	colorYellow = "\033[33m"
	colorBold   = "\033[1m"
)

func colorEnabled() bool {
	if noColor {
		return false
	}
	// Check if stdout is a terminal.
	info, err := os.Stdout.Stat()
	if err != nil {
		return false
	}
	return (info.Mode() & os.ModeCharDevice) != 0
}

func green(s string) string {
	if colorEnabled() {
		return colorGreen + s + colorReset
	}
	return s
}

func red(s string) string {
	if colorEnabled() {
		return colorRed + s + colorReset
	}
	return s
}

func yellow(s string) string {
	if colorEnabled() {
		return colorYellow + s + colorReset
	}
	return s
}

func bold(s string) string {
	if colorEnabled() {
		return colorBold + s + colorReset
	}
	return s
}

func checkMark() string {
	return green("\u2713")
}

func crossMark() string {
	return red("\u2717")
}

// joinHeadingPath formats a heading path like "Authentication > Token Storage".
func joinHeadingPath(path []string) string {
	return strings.Join(path, " > ")
}
