package git

import (
	"testing"
)

func TestParseUnifiedDiffSimple(t *testing.T) {
	diff := `diff --git a/src/main.go b/src/main.go
index 1234567..abcdefg 100644
--- a/src/main.go
+++ b/src/main.go
@@ -10,0 +11,3 @@ func main() {
+	fmt.Println("new line 1")
+	fmt.Println("new line 2")
+	fmt.Println("new line 3")
`

	result, err := ParseUnifiedDiff(diff)
	if err != nil {
		t.Fatalf("ParseUnifiedDiff() error: %v", err)
	}

	ranges, ok := result["src/main.go"]
	if !ok {
		t.Fatal("expected src/main.go in result")
	}

	if len(ranges) != 1 {
		t.Fatalf("expected 1 range, got %d", len(ranges))
	}

	if ranges[0].Start != 11 || ranges[0].End != 13 {
		t.Errorf("range = %d-%d, want 11-13", ranges[0].Start, ranges[0].End)
	}
}

func TestParseUnifiedDiffMultipleHunks(t *testing.T) {
	diff := `diff --git a/src/main.go b/src/main.go
--- a/src/main.go
+++ b/src/main.go
@@ -5,0 +5,2 @@
+line A
+line B
@@ -20,0 +22,1 @@
+line C
`

	result, err := ParseUnifiedDiff(diff)
	if err != nil {
		t.Fatalf("ParseUnifiedDiff() error: %v", err)
	}

	ranges := result["src/main.go"]
	if len(ranges) != 2 {
		t.Fatalf("expected 2 ranges, got %d", len(ranges))
	}

	if ranges[0].Start != 5 || ranges[0].End != 6 {
		t.Errorf("range[0] = %d-%d, want 5-6", ranges[0].Start, ranges[0].End)
	}
	if ranges[1].Start != 22 || ranges[1].End != 22 {
		t.Errorf("range[1] = %d-%d, want 22-22", ranges[1].Start, ranges[1].End)
	}
}

func TestParseUnifiedDiffMultipleFiles(t *testing.T) {
	diff := `diff --git a/src/main.go b/src/main.go
--- a/src/main.go
+++ b/src/main.go
@@ -1,0 +1,5 @@
+line1
+line2
+line3
+line4
+line5
diff --git a/src/util.go b/src/util.go
--- a/src/util.go
+++ b/src/util.go
@@ -10,0 +10,3 @@
+lineA
+lineB
+lineC
`

	result, err := ParseUnifiedDiff(diff)
	if err != nil {
		t.Fatalf("ParseUnifiedDiff() error: %v", err)
	}

	if len(result) != 2 {
		t.Fatalf("expected 2 files, got %d", len(result))
	}

	mainRanges := result["src/main.go"]
	if len(mainRanges) != 1 {
		t.Fatalf("src/main.go: expected 1 range, got %d", len(mainRanges))
	}
	if mainRanges[0].Start != 1 || mainRanges[0].End != 5 {
		t.Errorf("src/main.go range = %d-%d, want 1-5", mainRanges[0].Start, mainRanges[0].End)
	}

	utilRanges := result["src/util.go"]
	if len(utilRanges) != 1 {
		t.Fatalf("src/util.go: expected 1 range, got %d", len(utilRanges))
	}
	if utilRanges[0].Start != 10 || utilRanges[0].End != 12 {
		t.Errorf("src/util.go range = %d-%d, want 10-12", utilRanges[0].Start, utilRanges[0].End)
	}
}

func TestParseUnifiedDiffDeletion(t *testing.T) {
	// Pure deletion hunks (count=0 on the + side) should be skipped.
	diff := `diff --git a/src/main.go b/src/main.go
--- a/src/main.go
+++ b/src/main.go
@@ -5,3 +5,0 @@
-deleted line 1
-deleted line 2
-deleted line 3
`

	result, err := ParseUnifiedDiff(diff)
	if err != nil {
		t.Fatalf("ParseUnifiedDiff() error: %v", err)
	}

	ranges := result["src/main.go"]
	if len(ranges) != 0 {
		t.Errorf("expected 0 ranges for pure deletion, got %d", len(ranges))
	}
}

func TestParseUnifiedDiffEmpty(t *testing.T) {
	result, err := ParseUnifiedDiff("")
	if err != nil {
		t.Fatalf("ParseUnifiedDiff() error: %v", err)
	}

	if len(result) != 0 {
		t.Errorf("expected 0 files, got %d", len(result))
	}
}

func TestParseUnifiedDiffSingleLineAdd(t *testing.T) {
	// When only 1 line is added, the count is omitted in the hunk header.
	diff := `diff --git a/src/main.go b/src/main.go
--- a/src/main.go
+++ b/src/main.go
@@ -10,0 +11 @@
+single new line
`

	result, err := ParseUnifiedDiff(diff)
	if err != nil {
		t.Fatalf("ParseUnifiedDiff() error: %v", err)
	}

	ranges := result["src/main.go"]
	if len(ranges) != 1 {
		t.Fatalf("expected 1 range, got %d", len(ranges))
	}
	if ranges[0].Start != 11 || ranges[0].End != 11 {
		t.Errorf("range = %d-%d, want 11-11", ranges[0].Start, ranges[0].End)
	}
}

func TestParseUnifiedDiffModification(t *testing.T) {
	// A modification shows as delete + add.
	diff := `diff --git a/src/main.go b/src/main.go
--- a/src/main.go
+++ b/src/main.go
@@ -5,2 +5,3 @@
-old line 1
-old line 2
+new line 1
+new line 2
+new line 3
`

	result, err := ParseUnifiedDiff(diff)
	if err != nil {
		t.Fatalf("ParseUnifiedDiff() error: %v", err)
	}

	ranges := result["src/main.go"]
	if len(ranges) != 1 {
		t.Fatalf("expected 1 range, got %d", len(ranges))
	}
	if ranges[0].Start != 5 || ranges[0].End != 7 {
		t.Errorf("range = %d-%d, want 5-7", ranges[0].Start, ranges[0].End)
	}
}

func TestParseUnifiedDiffDeletedFile(t *testing.T) {
	diff := `diff --git a/src/old.go b/src/old.go
deleted file mode 100644
--- a/src/old.go
+++ /dev/null
@@ -1,5 +0,0 @@
-line1
-line2
-line3
-line4
-line5
`

	result, err := ParseUnifiedDiff(diff)
	if err != nil {
		t.Fatalf("ParseUnifiedDiff() error: %v", err)
	}

	// Deleted files (going to /dev/null) should not appear.
	if _, ok := result["src/old.go"]; ok {
		t.Error("deleted file should not be in result")
	}
	if _, ok := result["/dev/null"]; ok {
		t.Error("/dev/null should not be in result")
	}
}
