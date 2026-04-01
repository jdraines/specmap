package store

import (
	"context"
	"fmt"

	"github.com/specmap/specmap/api/internal/models"
)

// UpsertInstallation creates or updates an installation by GitHub ID.
func (s *Store) UpsertInstallation(ctx context.Context, githubID int64, accountLogin, accountType, repoSelection string) error {
	_, err := s.Pool.Exec(ctx, `
		INSERT INTO installations (github_id, account_login, account_type, repository_selection)
		VALUES ($1, $2, $3, $4)
		ON CONFLICT (github_id) DO UPDATE SET
			account_login = EXCLUDED.account_login,
			account_type = EXCLUDED.account_type,
			repository_selection = EXCLUDED.repository_selection,
			suspended_at = NULL,
			updated_at = now()
	`, githubID, accountLogin, accountType, repoSelection)
	if err != nil {
		return fmt.Errorf("upserting installation %d: %w", githubID, err)
	}
	return nil
}

// DeleteInstallation removes an installation by GitHub ID.
func (s *Store) DeleteInstallation(ctx context.Context, githubID int64) error {
	_, err := s.Pool.Exec(ctx, `DELETE FROM installations WHERE github_id = $1`, githubID)
	if err != nil {
		return fmt.Errorf("deleting installation %d: %w", githubID, err)
	}
	return nil
}

// SuspendInstallation marks an installation as suspended.
func (s *Store) SuspendInstallation(ctx context.Context, githubID int64) error {
	_, err := s.Pool.Exec(ctx, `UPDATE installations SET suspended_at = now(), updated_at = now() WHERE github_id = $1`, githubID)
	if err != nil {
		return fmt.Errorf("suspending installation %d: %w", githubID, err)
	}
	return nil
}

// UnsuspendInstallation clears the suspended_at field on an installation.
func (s *Store) UnsuspendInstallation(ctx context.Context, githubID int64) error {
	_, err := s.Pool.Exec(ctx, `UPDATE installations SET suspended_at = NULL, updated_at = now() WHERE github_id = $1`, githubID)
	if err != nil {
		return fmt.Errorf("unsuspending installation %d: %w", githubID, err)
	}
	return nil
}

// ListInstallations returns all installations.
func (s *Store) ListInstallations(ctx context.Context) ([]models.Installation, error) {
	rows, err := s.Pool.Query(ctx, `
		SELECT id, github_id, account_login, account_type, repository_selection, suspended_at, created_at, updated_at
		FROM installations ORDER BY created_at DESC
	`)
	if err != nil {
		return nil, fmt.Errorf("listing installations: %w", err)
	}
	defer rows.Close()

	var installations []models.Installation
	for rows.Next() {
		var inst models.Installation
		if err := rows.Scan(&inst.ID, &inst.GitHubID, &inst.AccountLogin, &inst.AccountType, &inst.RepositorySelection, &inst.SuspendedAt, &inst.CreatedAt, &inst.UpdatedAt); err != nil {
			return nil, fmt.Errorf("scanning installation: %w", err)
		}
		installations = append(installations, inst)
	}
	return installations, nil
}

// GetInstallationByAccount returns an installation by account login.
func (s *Store) GetInstallationByAccount(ctx context.Context, login string) (*models.Installation, error) {
	inst := &models.Installation{}
	err := s.Pool.QueryRow(ctx, `
		SELECT id, github_id, account_login, account_type, repository_selection, suspended_at, created_at, updated_at
		FROM installations WHERE account_login = $1
	`, login).Scan(&inst.ID, &inst.GitHubID, &inst.AccountLogin, &inst.AccountType, &inst.RepositorySelection, &inst.SuspendedAt, &inst.CreatedAt, &inst.UpdatedAt)
	if err != nil {
		return nil, fmt.Errorf("getting installation for %s: %w", login, err)
	}
	return inst, nil
}
