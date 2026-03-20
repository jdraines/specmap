package store

import (
	"context"
	"fmt"

	"github.com/specmap/specmap/api/internal/models"
)

// UpsertUser creates or updates a user by GitHub ID. Returns the user with its DB id.
func (s *Store) UpsertUser(ctx context.Context, u *models.User) (*models.User, error) {
	row := s.Pool.QueryRow(ctx, `
		INSERT INTO users (github_id, login, name, avatar_url)
		VALUES ($1, $2, $3, $4)
		ON CONFLICT (github_id) DO UPDATE SET
			login = EXCLUDED.login,
			name = EXCLUDED.name,
			avatar_url = EXCLUDED.avatar_url,
			updated_at = now()
		RETURNING id, created_at, updated_at
	`, u.GitHubID, u.Login, u.Name, u.AvatarURL)

	if err := row.Scan(&u.ID, &u.CreatedAt, &u.UpdatedAt); err != nil {
		return nil, fmt.Errorf("upserting user: %w", err)
	}
	return u, nil
}

// GetUserByID returns a user by their database ID.
func (s *Store) GetUserByID(ctx context.Context, id int64) (*models.User, error) {
	u := &models.User{}
	err := s.Pool.QueryRow(ctx, `
		SELECT id, github_id, login, name, avatar_url, created_at, updated_at
		FROM users WHERE id = $1
	`, id).Scan(&u.ID, &u.GitHubID, &u.Login, &u.Name, &u.AvatarURL, &u.CreatedAt, &u.UpdatedAt)
	if err != nil {
		return nil, fmt.Errorf("getting user %d: %w", id, err)
	}
	return u, nil
}

// UpsertToken stores an encrypted OAuth token for a user (one token per user).
func (s *Store) UpsertToken(ctx context.Context, userID int64, encryptedToken []byte, tokenType, scope string) error {
	_, err := s.Pool.Exec(ctx, `
		INSERT INTO user_tokens (user_id, access_token_encrypted, token_type, scope)
		VALUES ($1, $2, $3, $4)
		ON CONFLICT (user_id) DO UPDATE SET
			access_token_encrypted = EXCLUDED.access_token_encrypted,
			token_type = EXCLUDED.token_type,
			scope = EXCLUDED.scope,
			updated_at = now()
	`, userID, encryptedToken, tokenType, scope)
	if err != nil {
		return fmt.Errorf("upserting token for user %d: %w", userID, err)
	}
	return nil
}

// GetToken returns the encrypted token for a user.
func (s *Store) GetToken(ctx context.Context, userID int64) ([]byte, error) {
	var encrypted []byte
	err := s.Pool.QueryRow(ctx, `
		SELECT access_token_encrypted FROM user_tokens WHERE user_id = $1
	`, userID).Scan(&encrypted)
	if err != nil {
		return nil, fmt.Errorf("getting token for user %d: %w", userID, err)
	}
	return encrypted, nil
}
