package auth

import (
	"crypto/rand"
	"encoding/hex"
	"testing"
)

func testKey(t *testing.T) string {
	t.Helper()
	key := make([]byte, 32)
	if _, err := rand.Read(key); err != nil {
		t.Fatal(err)
	}
	return hex.EncodeToString(key)
}

func TestEncryptDecryptRoundtrip(t *testing.T) {
	key := testKey(t)
	plaintext := []byte("my-secret-oauth-token")

	ciphertext, err := Encrypt(plaintext, key)
	if err != nil {
		t.Fatalf("encrypt: %v", err)
	}

	if string(ciphertext) == string(plaintext) {
		t.Fatal("ciphertext should not equal plaintext")
	}

	decrypted, err := Decrypt(ciphertext, key)
	if err != nil {
		t.Fatalf("decrypt: %v", err)
	}

	if string(decrypted) != string(plaintext) {
		t.Fatalf("got %q, want %q", decrypted, plaintext)
	}
}

func TestEncryptDifferentCiphertexts(t *testing.T) {
	key := testKey(t)
	plaintext := []byte("same-input")

	c1, _ := Encrypt(plaintext, key)
	c2, _ := Encrypt(plaintext, key)

	if string(c1) == string(c2) {
		t.Fatal("two encryptions of the same plaintext should produce different ciphertexts (random nonce)")
	}
}

func TestDecryptWrongKey(t *testing.T) {
	key1 := testKey(t)
	key2 := testKey(t)

	ciphertext, _ := Encrypt([]byte("secret"), key1)

	_, err := Decrypt(ciphertext, key2)
	if err == nil {
		t.Fatal("decryption with wrong key should fail")
	}
}

func TestEncryptBadKeyLength(t *testing.T) {
	_, err := Encrypt([]byte("test"), "0011223344") // too short
	if err == nil {
		t.Fatal("should reject short key")
	}
}
