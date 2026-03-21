package store

import (
	"context"
	"errors"
	"fmt"

	"github.com/jackc/pgx/v5"

	"github.com/specmap/specmap/api/internal/models"
)

// GetMappingCache returns a cached specmap result for a PR at a specific head SHA.
// Returns nil, nil on cache miss.
func (s *Store) GetMappingCache(ctx context.Context, pullRequestID int64, headSHA string) (*models.MappingCache, error) {
	mc := &models.MappingCache{}
	err := s.Pool.QueryRow(ctx, `
		SELECT id, pull_request_id, head_sha, specmap_json, created_at
		FROM mapping_cache
		WHERE pull_request_id = $1 AND head_sha = $2
	`, pullRequestID, headSHA).Scan(&mc.ID, &mc.PullRequestID, &mc.HeadSHA, &mc.SpecmapJSON, &mc.CreatedAt)
	if err != nil {
		if errors.Is(err, pgx.ErrNoRows) {
			return nil, nil
		}
		return nil, fmt.Errorf("getting mapping cache for PR %d @ %s: %w", pullRequestID, headSHA, err)
	}
	return mc, nil
}

// UpsertMappingCache creates or updates a mapping cache entry.
func (s *Store) UpsertMappingCache(ctx context.Context, mc *models.MappingCache) (*models.MappingCache, error) {
	row := s.Pool.QueryRow(ctx, `
		INSERT INTO mapping_cache (pull_request_id, head_sha, specmap_json)
		VALUES ($1, $2, $3)
		ON CONFLICT (pull_request_id, head_sha) DO UPDATE SET
			specmap_json = EXCLUDED.specmap_json
		RETURNING id, created_at
	`, mc.PullRequestID, mc.HeadSHA, mc.SpecmapJSON)

	if err := row.Scan(&mc.ID, &mc.CreatedAt); err != nil {
		return nil, fmt.Errorf("upserting mapping cache: %w", err)
	}
	return mc, nil
}
