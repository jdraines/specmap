package store

import (
	"context"
	"fmt"

	"github.com/specmap/specmap/api/internal/models"
)

// UpsertPull creates or updates a pull request by repo ID + number.
func (s *Store) UpsertPull(ctx context.Context, p *models.PullRequest) (*models.PullRequest, error) {
	row := s.Pool.QueryRow(ctx, `
		INSERT INTO pull_requests (repository_id, number, title, state, head_branch, base_branch, head_sha, author_login)
		VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
		ON CONFLICT (repository_id, number) DO UPDATE SET
			title = EXCLUDED.title,
			state = EXCLUDED.state,
			head_branch = EXCLUDED.head_branch,
			base_branch = EXCLUDED.base_branch,
			head_sha = EXCLUDED.head_sha,
			author_login = EXCLUDED.author_login,
			updated_at = now()
		RETURNING id, created_at, updated_at
	`, p.RepositoryID, p.Number, p.Title, p.State, p.HeadBranch, p.BaseBranch, p.HeadSHA, p.AuthorLogin)

	if err := row.Scan(&p.ID, &p.CreatedAt, &p.UpdatedAt); err != nil {
		return nil, fmt.Errorf("upserting pull: %w", err)
	}
	return p, nil
}

// ListPullsByRepo returns pull requests for a repository.
func (s *Store) ListPullsByRepo(ctx context.Context, repoID int64) ([]models.PullRequest, error) {
	rows, err := s.Pool.Query(ctx, `
		SELECT id, repository_id, number, title, state, head_branch, base_branch,
		       head_sha, author_login, created_at, updated_at
		FROM pull_requests
		WHERE repository_id = $1
		ORDER BY number DESC
	`, repoID)
	if err != nil {
		return nil, fmt.Errorf("listing pulls for repo %d: %w", repoID, err)
	}
	defer rows.Close()

	var pulls []models.PullRequest
	for rows.Next() {
		var p models.PullRequest
		if err := rows.Scan(&p.ID, &p.RepositoryID, &p.Number, &p.Title, &p.State,
			&p.HeadBranch, &p.BaseBranch, &p.HeadSHA, &p.AuthorLogin,
			&p.CreatedAt, &p.UpdatedAt); err != nil {
			return nil, fmt.Errorf("scanning pull: %w", err)
		}
		pulls = append(pulls, p)
	}
	return pulls, rows.Err()
}

// GetPull returns a single pull request by repo ID and number.
func (s *Store) GetPull(ctx context.Context, repoID int64, number int) (*models.PullRequest, error) {
	p := &models.PullRequest{}
	err := s.Pool.QueryRow(ctx, `
		SELECT id, repository_id, number, title, state, head_branch, base_branch,
		       head_sha, author_login, created_at, updated_at
		FROM pull_requests
		WHERE repository_id = $1 AND number = $2
	`, repoID, number).Scan(&p.ID, &p.RepositoryID, &p.Number, &p.Title, &p.State,
		&p.HeadBranch, &p.BaseBranch, &p.HeadSHA, &p.AuthorLogin,
		&p.CreatedAt, &p.UpdatedAt)
	if err != nil {
		return nil, fmt.Errorf("getting pull %d#%d: %w", repoID, number, err)
	}
	return p, nil
}
