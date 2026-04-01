package github

import (
	"crypto/rand"
	"crypto/rsa"
	"crypto/x509"
	"encoding/pem"
	"testing"

	"github.com/golang-jwt/jwt/v5"
)

func generateTestKey(t *testing.T) (*rsa.PrivateKey, []byte) {
	t.Helper()
	key, err := rsa.GenerateKey(rand.Reader, 2048)
	if err != nil {
		t.Fatalf("generating test key: %v", err)
	}
	pemBytes := pem.EncodeToMemory(&pem.Block{
		Type:  "RSA PRIVATE KEY",
		Bytes: x509.MarshalPKCS1PrivateKey(key),
	})
	return key, pemBytes
}

func TestNewAppAuth(t *testing.T) {
	_, pemBytes := generateTestKey(t)

	auth, err := NewAppAuth(12345, pemBytes)
	if err != nil {
		t.Fatalf("NewAppAuth failed: %v", err)
	}
	if auth.AppID != 12345 {
		t.Errorf("expected AppID 12345, got %d", auth.AppID)
	}
}

func TestNewAppAuth_InvalidPEM(t *testing.T) {
	_, err := NewAppAuth(1, []byte("not a pem key"))
	if err == nil {
		t.Fatal("expected error for invalid PEM")
	}
}

func TestGenerateJWT(t *testing.T) {
	key, pemBytes := generateTestKey(t)

	auth, err := NewAppAuth(42, pemBytes)
	if err != nil {
		t.Fatalf("NewAppAuth failed: %v", err)
	}

	tokenStr, err := auth.GenerateJWT()
	if err != nil {
		t.Fatalf("GenerateJWT failed: %v", err)
	}

	// Parse and verify the token.
	token, err := jwt.ParseWithClaims(tokenStr, &jwt.RegisteredClaims{}, func(t *jwt.Token) (any, error) {
		return &key.PublicKey, nil
	})
	if err != nil {
		t.Fatalf("parsing generated JWT: %v", err)
	}

	claims, ok := token.Claims.(*jwt.RegisteredClaims)
	if !ok || !token.Valid {
		t.Fatal("invalid token")
	}

	if claims.Issuer != "42" {
		t.Errorf("expected issuer '42', got %q", claims.Issuer)
	}
}

func TestGenerateJWT_SigningMethod(t *testing.T) {
	_, pemBytes := generateTestKey(t)

	auth, err := NewAppAuth(1, pemBytes)
	if err != nil {
		t.Fatalf("NewAppAuth failed: %v", err)
	}

	tokenStr, err := auth.GenerateJWT()
	if err != nil {
		t.Fatalf("GenerateJWT failed: %v", err)
	}

	// Parse without verification to check the header.
	parser := jwt.NewParser(jwt.WithoutClaimsValidation())
	token, _, err := parser.ParseUnverified(tokenStr, &jwt.RegisteredClaims{})
	if err != nil {
		t.Fatalf("parsing JWT header: %v", err)
	}

	if token.Method.Alg() != "RS256" {
		t.Errorf("expected RS256, got %s", token.Method.Alg())
	}
}
