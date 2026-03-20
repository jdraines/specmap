package auth

import (
	"fmt"
	"time"

	"github.com/golang-jwt/jwt/v5"

	"github.com/specmap/specmap/api/internal/models"
)

const sessionDuration = 1 * time.Hour

// Claims are the JWT claims for a specmap session.
type Claims struct {
	jwt.RegisteredClaims
	UserID    int64  `json:"uid"`
	Login     string `json:"login"`
	AvatarURL string `json:"avatar"`
}

// CreateToken creates a signed JWT for the given session.
func CreateToken(session *models.Session, secret string) (string, error) {
	now := time.Now()
	claims := &Claims{
		RegisteredClaims: jwt.RegisteredClaims{
			IssuedAt:  jwt.NewNumericDate(now),
			ExpiresAt: jwt.NewNumericDate(now.Add(sessionDuration)),
			Issuer:    "specmap",
		},
		UserID:    session.UserID,
		Login:     session.Login,
		AvatarURL: session.AvatarURL,
	}

	token := jwt.NewWithClaims(jwt.SigningMethodHS256, claims)
	signed, err := token.SignedString([]byte(secret))
	if err != nil {
		return "", fmt.Errorf("signing JWT: %w", err)
	}
	return signed, nil
}

// ValidateToken parses and validates a JWT, returning the claims.
func ValidateToken(tokenStr, secret string) (*Claims, error) {
	token, err := jwt.ParseWithClaims(tokenStr, &Claims{}, func(t *jwt.Token) (any, error) {
		if _, ok := t.Method.(*jwt.SigningMethodHMAC); !ok {
			return nil, fmt.Errorf("unexpected signing method: %v", t.Header["alg"])
		}
		return []byte(secret), nil
	})
	if err != nil {
		return nil, fmt.Errorf("parsing JWT: %w", err)
	}

	claims, ok := token.Claims.(*Claims)
	if !ok || !token.Valid {
		return nil, fmt.Errorf("invalid token")
	}
	return claims, nil
}
