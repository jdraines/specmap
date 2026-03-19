package git

import (
	"bufio"
	"fmt"
	"os/exec"
	"path/filepath"
	"regexp"
	"strconv"
	"strings"
)

// LineRange represents a range of line numbers.
type LineRange struct {
	Start int
	End   int
}

// ChangedFiles runs git diff and returns changed line ranges per file.
// base is the base ref (e.g. "main"). It runs git diff base...HEAD with
// unified context of 0 to get exact changed line ranges.
func ChangedFiles(repoRoot, base string) (map[string][]LineRange, error) {
	absRoot, err := filepath.Abs(repoRoot)
	if err != nil {
		return nil, fmt.Errorf("resolving repo root: %w", err)
	}

	// Run git diff -U0 base...HEAD to get exact line ranges.
	cmd := exec.Command("git", "diff", "-U0", base+"...HEAD")
	cmd.Dir = absRoot
	out, err := cmd.Output()
	if err != nil {
		return nil, fmt.Errorf("running git diff: %w", err)
	}

	return ParseUnifiedDiff(string(out))
}

// ParseUnifiedDiff parses unified diff output (with -U0) and extracts
// added/modified line ranges per file.
func ParseUnifiedDiff(diff string) (map[string][]LineRange, error) {
	result := make(map[string][]LineRange)

	// Match the +++ b/path lines to get file names.
	fileRe := regexp.MustCompile(`^\+\+\+ b/(.+)$`)
	// Match @@ hunk headers. Format: @@ -old,count +new,count @@
	// With -U0, the +new,count tells us exactly which lines were added/modified.
	hunkRe := regexp.MustCompile(`^@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@`)

	var currentFile string

	scanner := bufio.NewScanner(strings.NewReader(diff))
	for scanner.Scan() {
		line := scanner.Text()

		if m := fileRe.FindStringSubmatch(line); m != nil {
			currentFile = m[1]
			// Skip /dev/null (deleted files).
			if currentFile == "/dev/null" {
				currentFile = ""
			}
			continue
		}

		if currentFile == "" {
			continue
		}

		if m := hunkRe.FindStringSubmatch(line); m != nil {
			start, err := strconv.Atoi(m[1])
			if err != nil {
				continue
			}
			count := 1
			if m[2] != "" {
				count, err = strconv.Atoi(m[2])
				if err != nil {
					continue
				}
			}
			// A count of 0 means pure deletion at this position in the new file;
			// no new lines to cover.
			if count == 0 {
				continue
			}
			end := start + count - 1
			result[currentFile] = append(result[currentFile], LineRange{Start: start, End: end})
		}
	}

	return result, scanner.Err()
}

// CurrentBranch returns the current git branch name by reading .git/HEAD.
func CurrentBranch(repoRoot string) (string, error) {
	absRoot, err := filepath.Abs(repoRoot)
	if err != nil {
		return "", fmt.Errorf("resolving repo root: %w", err)
	}

	cmd := exec.Command("git", "rev-parse", "--abbrev-ref", "HEAD")
	cmd.Dir = absRoot
	out, err := cmd.Output()
	if err != nil {
		return "", fmt.Errorf("detecting branch: %w", err)
	}

	branch := strings.TrimSpace(string(out))
	if branch == "" || branch == "HEAD" {
		return "", fmt.Errorf("could not determine branch name (detached HEAD?)")
	}
	return branch, nil
}
