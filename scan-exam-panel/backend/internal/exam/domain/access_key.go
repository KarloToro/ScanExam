package domain

import (
	"crypto/rand"
	"encoding/base64"
)

// NewAccessKey returns a URL-safe random access key (~22 characters).
func NewAccessKey() (string, error) {
	buf := make([]byte, 16)
	if _, err := rand.Read(buf); err != nil {
		return "", err
	}
	return base64.RawURLEncoding.EncodeToString(buf), nil
}
