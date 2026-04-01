package auth

import (
	"crypto/rand"
	"encoding/hex"
	"fmt"
	"io"
	"net/http"
	"net/url"
	"time"
)

const (
	githubAuthorizeURL = "https://github.com/login/oauth/authorize"
	stateCookieName    = "specmap_oauth_state"
	sessionCookieName  = "specmap_session"
)

// OAuthConfig holds GitHub OAuth parameters.
type OAuthConfig struct {
	ClientID     string
	ClientSecret string
	BaseURL      string // our server's base URL for the callback
}

// LoginURL generates the GitHub OAuth authorization URL with a random state.
// It also returns an http.Cookie that should be set to store the state for CSRF verification.
func (c *OAuthConfig) LoginURL() (string, *http.Cookie, error) {
	state, err := randomHex(16)
	if err != nil {
		return "", nil, fmt.Errorf("generating state: %w", err)
	}

	u, _ := url.Parse(githubAuthorizeURL)
	q := u.Query()
	q.Set("client_id", c.ClientID)
	q.Set("redirect_uri", c.BaseURL+"/api/v1/auth/callback")
	q.Set("state", state)
	u.RawQuery = q.Encode()

	cookie := &http.Cookie{
		Name:     stateCookieName,
		Value:    state,
		Path:     "/",
		HttpOnly: true,
		Secure:   true,
		SameSite: http.SameSiteLaxMode,
		MaxAge:   600, // 10 minutes
	}

	return u.String(), cookie, nil
}

// SessionCookie creates the session cookie containing the JWT.
func SessionCookie(token string) *http.Cookie {
	return &http.Cookie{
		Name:     sessionCookieName,
		Value:    token,
		Path:     "/",
		HttpOnly: true,
		Secure:   true,
		SameSite: http.SameSiteLaxMode,
		MaxAge:   int(time.Hour.Seconds()),
	}
}

// ClearSessionCookie returns a cookie that clears the session.
func ClearSessionCookie() *http.Cookie {
	return &http.Cookie{
		Name:     sessionCookieName,
		Value:    "",
		Path:     "/",
		HttpOnly: true,
		Secure:   true,
		SameSite: http.SameSiteLaxMode,
		MaxAge:   -1,
	}
}

// GetSessionCookie extracts the session JWT from the request.
func GetSessionCookie(r *http.Request) (string, error) {
	c, err := r.Cookie(sessionCookieName)
	if err != nil {
		return "", err
	}
	return c.Value, nil
}

// GetStateCookie extracts the OAuth state from the request cookie.
func GetStateCookie(r *http.Request) (string, error) {
	c, err := r.Cookie(stateCookieName)
	if err != nil {
		return "", err
	}
	return c.Value, nil
}

func randomHex(n int) (string, error) {
	b := make([]byte, n)
	if _, err := io.ReadFull(rand.Reader, b); err != nil {
		return "", err
	}
	return hex.EncodeToString(b), nil
}
