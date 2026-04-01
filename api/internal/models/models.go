// Package models defines the domain types for the specmap API.
package models

import "time"

// User is a specmap user linked to a GitHub account.
type User struct {
	ID        int64     `json:"id"`
	GitHubID  int64     `json:"github_id"`
	Login     string    `json:"login"`
	Name      string    `json:"name"`
	AvatarURL string    `json:"avatar_url"`
	CreatedAt time.Time `json:"created_at"`
	UpdatedAt time.Time `json:"updated_at"`
}

// UserToken stores encrypted OAuth tokens for a user.
type UserToken struct {
	ID                  int64     `json:"-"`
	UserID              int64     `json:"-"`
	AccessTokenEncrypted string  `json:"-"` // AES-256-GCM encrypted
	TokenType           string    `json:"-"`
	Scope               string    `json:"-"`
	CreatedAt           time.Time `json:"-"`
	UpdatedAt           time.Time `json:"-"`
}

// Repository is a GitHub repo the user has access to.
type Repository struct {
	ID        int64     `json:"id"`
	GitHubID  int64     `json:"github_id"`
	Owner     string    `json:"owner"`
	Name      string    `json:"name"`
	FullName  string    `json:"full_name"`
	Private   bool      `json:"private"`
	CreatedAt time.Time `json:"created_at"`
	UpdatedAt time.Time `json:"updated_at"`
}

// PullRequest is cached PR metadata.
type PullRequest struct {
	ID           int64     `json:"id"`
	RepositoryID int64     `json:"repository_id"`
	Number       int       `json:"number"`
	Title        string    `json:"title"`
	State        string    `json:"state"` // open, closed, merged
	HeadBranch   string    `json:"head_branch"`
	BaseBranch   string    `json:"base_branch"`
	HeadSHA      string    `json:"head_sha"`
	AuthorLogin  string    `json:"author_login"`
	CreatedAt    time.Time `json:"created_at"`
	UpdatedAt    time.Time `json:"updated_at"`
}

// MappingCache caches .specmap/ data keyed by PR + head SHA.
type MappingCache struct {
	ID            int64     `json:"id"`
	PullRequestID int64    `json:"pull_request_id"`
	HeadSHA       string    `json:"head_sha"`
	SpecmapJSON   []byte    `json:"-"` // raw JSON content
	CreatedAt     time.Time `json:"created_at"`
}

// Installation represents a GitHub App installation on a user or organization account.
type Installation struct {
	ID                  int64      `json:"id"`
	GitHubID            int64      `json:"github_id"`
	AccountLogin        string     `json:"account_login"`
	AccountType         string     `json:"account_type"`
	RepositorySelection string     `json:"repository_selection"`
	SuspendedAt         *time.Time `json:"suspended_at"`
	CreatedAt           time.Time  `json:"created_at"`
	UpdatedAt           time.Time  `json:"updated_at"`
}

// Session represents a user's authenticated session (stored as JWT claims, not in DB).
type Session struct {
	UserID    int64  `json:"user_id"`
	Login     string `json:"login"`
	AvatarURL string `json:"avatar_url"`
}

// SpecRef is an inline citation to a spec document within an annotation.
type SpecRef struct {
	ID        int    `json:"id"`
	SpecFile  string `json:"spec_file"`
	Heading   string `json:"heading"`
	StartLine int    `json:"start_line"`
	Excerpt   string `json:"excerpt"`
}

// Annotation describes a code change region with inline spec references.
type Annotation struct {
	ID          string    `json:"id"`
	File        string    `json:"file"`
	StartLine   int       `json:"start_line"`
	EndLine     int       `json:"end_line"`
	Description string    `json:"description"`
	Refs        []SpecRef `json:"refs"`
	CreatedAt   time.Time `json:"created_at"`
}

// SpecmapFileV2 is the persisted .specmap/{branch}.json format (v2: annotation-based).
type SpecmapFileV2 struct {
	Version        int          `json:"version"`
	Branch         string       `json:"branch"`
	BaseBranch     string       `json:"base_branch"`
	HeadSHA        string       `json:"head_sha"`
	UpdatedAt      time.Time    `json:"updated_at"`
	UpdatedBy      string       `json:"updated_by"`
	Annotations    []Annotation `json:"annotations"`
	IgnorePatterns []string     `json:"ignore_patterns"`
}
