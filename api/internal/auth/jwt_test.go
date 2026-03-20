package auth

import (
	"testing"

	"github.com/specmap/specmap/api/internal/models"
)

const testSecret = "test-secret-that-is-long-enough-for-hmac"

func TestCreateAndValidateToken(t *testing.T) {
	session := &models.Session{
		UserID:    42,
		Login:     "testuser",
		AvatarURL: "https://example.com/avatar.png",
	}

	token, err := CreateToken(session, testSecret)
	if err != nil {
		t.Fatalf("create: %v", err)
	}

	claims, err := ValidateToken(token, testSecret)
	if err != nil {
		t.Fatalf("validate: %v", err)
	}

	if claims.UserID != 42 {
		t.Errorf("UserID = %d, want 42", claims.UserID)
	}
	if claims.Login != "testuser" {
		t.Errorf("Login = %q, want %q", claims.Login, "testuser")
	}
	if claims.AvatarURL != "https://example.com/avatar.png" {
		t.Errorf("AvatarURL = %q, want %q", claims.AvatarURL, "https://example.com/avatar.png")
	}
}

func TestValidateTokenWrongSecret(t *testing.T) {
	session := &models.Session{UserID: 1, Login: "user"}

	token, _ := CreateToken(session, testSecret)
	_, err := ValidateToken(token, "wrong-secret")
	if err == nil {
		t.Fatal("validation with wrong secret should fail")
	}
}

func TestValidateTokenGarbage(t *testing.T) {
	_, err := ValidateToken("not-a-jwt", testSecret)
	if err == nil {
		t.Fatal("garbage token should fail validation")
	}
}
