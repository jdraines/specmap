package github

import (
	"context"
	"crypto/rsa"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"time"

	"github.com/golang-jwt/jwt/v5"
)

const apiBaseURL = "https://api.github.com"

// AppAuth provides GitHub App authentication via JWT and installation tokens.
type AppAuth struct {
	AppID      int64
	PrivateKey *rsa.PrivateKey
}

// InstallationToken is the response from creating an installation access token.
type InstallationToken struct {
	Token     string    `json:"token"`
	ExpiresAt time.Time `json:"expires_at"`
}

// NewAppAuth parses a PEM-encoded RSA private key and returns an AppAuth.
func NewAppAuth(appID int64, privateKeyPEM []byte) (*AppAuth, error) {
	key, err := jwt.ParseRSAPrivateKeyFromPEM(privateKeyPEM)
	if err != nil {
		return nil, fmt.Errorf("parsing private key: %w", err)
	}
	return &AppAuth{AppID: appID, PrivateKey: key}, nil
}

// GenerateJWT creates a signed JWT for authenticating as the GitHub App.
func (a *AppAuth) GenerateJWT() (string, error) {
	now := time.Now()
	claims := &jwt.RegisteredClaims{
		Issuer:    fmt.Sprintf("%d", a.AppID),
		IssuedAt:  jwt.NewNumericDate(now.Add(-60 * time.Second)),
		ExpiresAt: jwt.NewNumericDate(now.Add(10 * time.Minute)),
	}

	token := jwt.NewWithClaims(jwt.SigningMethodRS256, claims)
	signed, err := token.SignedString(a.PrivateKey)
	if err != nil {
		return "", fmt.Errorf("signing app JWT: %w", err)
	}
	return signed, nil
}

// CreateInstallationToken exchanges the App JWT for an installation access token.
func (a *AppAuth) CreateInstallationToken(ctx context.Context, installationID int64) (*InstallationToken, error) {
	appJWT, err := a.GenerateJWT()
	if err != nil {
		return nil, err
	}

	url := fmt.Sprintf("%s/app/installations/%d/access_tokens", apiBaseURL, installationID)
	req, err := http.NewRequestWithContext(ctx, http.MethodPost, url, nil)
	if err != nil {
		return nil, fmt.Errorf("creating installation token request: %w", err)
	}
	req.Header.Set("Authorization", "Bearer "+appJWT)
	req.Header.Set("Accept", "application/vnd.github+json")

	resp, err := http.DefaultClient.Do(req)
	if err != nil {
		return nil, fmt.Errorf("requesting installation token: %w", err)
	}
	defer resp.Body.Close()

	body, err := io.ReadAll(resp.Body)
	if err != nil {
		return nil, fmt.Errorf("reading installation token response: %w", err)
	}

	if resp.StatusCode != http.StatusCreated {
		return nil, fmt.Errorf("installation token request failed (%d): %s", resp.StatusCode, body)
	}

	var token InstallationToken
	if err := json.Unmarshal(body, &token); err != nil {
		return nil, fmt.Errorf("parsing installation token response: %w", err)
	}

	return &token, nil
}
