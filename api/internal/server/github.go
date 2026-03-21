package server

import (
	"context"

	"github.com/specmap/specmap/api/internal/github"
)

// GitHubAPI abstracts the GitHub API calls needed by handlers.
// The real implementation delegates to the github package functions.
// Tests can inject a mock.
type GitHubAPI interface {
	GetPull(ctx context.Context, accessToken, owner, repo string, number int) (*github.Pull, error)
	GetRepo(ctx context.Context, accessToken, owner, name string) (*github.Repo, error)
	ListPulls(ctx context.Context, accessToken, owner, repo string) ([]github.Pull, error)
	ListRepos(ctx context.Context, accessToken string) ([]github.Repo, error)
	ListPullFiles(ctx context.Context, accessToken, owner, repo string, number int) ([]github.PullFile, error)
	GetFileContent(ctx context.Context, accessToken, owner, repo, path, ref string) ([]byte, error)
}

// realGitHub delegates to the github package functions.
type realGitHub struct{}

func (realGitHub) GetPull(ctx context.Context, accessToken, owner, repo string, number int) (*github.Pull, error) {
	return github.GetPull(ctx, accessToken, owner, repo, number)
}

func (realGitHub) GetRepo(ctx context.Context, accessToken, owner, name string) (*github.Repo, error) {
	return github.GetRepo(ctx, accessToken, owner, name)
}

func (realGitHub) ListPulls(ctx context.Context, accessToken, owner, repo string) ([]github.Pull, error) {
	return github.ListPulls(ctx, accessToken, owner, repo)
}

func (realGitHub) ListRepos(ctx context.Context, accessToken string) ([]github.Repo, error) {
	return github.ListRepos(ctx, accessToken)
}

func (realGitHub) ListPullFiles(ctx context.Context, accessToken, owner, repo string, number int) ([]github.PullFile, error) {
	return github.ListPullFiles(ctx, accessToken, owner, repo, number)
}

func (realGitHub) GetFileContent(ctx context.Context, accessToken, owner, repo, path, ref string) ([]byte, error) {
	return github.GetFileContent(ctx, accessToken, owner, repo, path, ref)
}
