package store

import (
	"context"
	"fmt"

	"github.com/specmap/specmap/api/internal/models"
)

// UpsertRepo creates or updates a repository by GitHub ID.
func (s *Store) UpsertRepo(ctx context.Context, r *models.Repository) (*models.Repository, error) {
	row := s.Pool.QueryRow(ctx, `
		INSERT INTO repositories (github_id, owner, name, full_name, private)
		VALUES ($1, $2, $3, $4, $5)
		ON CONFLICT (github_id) DO UPDATE SET
			owner = EXCLUDED.owner,
			name = EXCLUDED.name,
			full_name = EXCLUDED.full_name,
			private = EXCLUDED.private,
			updated_at = now()
		RETURNING id, created_at, updated_at
	`, r.GitHubID, r.Owner, r.Name, r.FullName, r.Private)

	if err := row.Scan(&r.ID, &r.CreatedAt, &r.UpdatedAt); err != nil {
		return nil, fmt.Errorf("upserting repo: %w", err)
	}
	return r, nil
}

// GetRepoByFullName returns a repository by owner/name.
func (s *Store) GetRepoByFullName(ctx context.Context, owner, name string) (*models.Repository, error) {
	r := &models.Repository{}
	err := s.Pool.QueryRow(ctx, `
		SELECT id, github_id, owner, name, full_name, private, created_at, updated_at
		FROM repositories WHERE owner = $1 AND name = $2
	`, owner, name).Scan(&r.ID, &r.GitHubID, &r.Owner, &r.Name, &r.FullName, &r.Private, &r.CreatedAt, &r.UpdatedAt)
	if err != nil {
		return nil, fmt.Errorf("getting repo %s/%s: %w", owner, name, err)
	}
	return r, nil
}
