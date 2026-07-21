package application

import (
	"fmt"
	"time"

	"scan-exam-api/internal/auth/domain"

	"github.com/golang-jwt/jwt/v5"
)

type JWTService struct {
	secret []byte
	ttl    time.Duration
}

func NewJWTService(secret string, ttl time.Duration) *JWTService {
	return &JWTService{
		secret: []byte(secret),
		ttl:    ttl,
	}
}

func (s *JWTService) TTL() time.Duration {
	return s.ttl
}

func (s *JWTService) Sign(userID, username, email string) (string, error) {
	now := time.Now()
	claims := domain.Claims{
		Username: username,
		Email:    email,
		RegisteredClaims: jwt.RegisteredClaims{
			Subject:   userID,
			IssuedAt:  jwt.NewNumericDate(now),
			ExpiresAt: jwt.NewNumericDate(now.Add(s.ttl)),
		},
	}

	token := jwt.NewWithClaims(jwt.SigningMethodHS256, claims)
	return token.SignedString(s.secret)
}

func (s *JWTService) Verify(tokenString string) (*domain.Claims, error) {
	token, err := jwt.ParseWithClaims(tokenString, &domain.Claims{}, func(token *jwt.Token) (any, error) {
		if token.Method != jwt.SigningMethodHS256 {
			return nil, fmt.Errorf("%w: unexpected signing method", domain.ErrInvalidToken)
		}
		return s.secret, nil
	})
	if err != nil {
		return nil, domain.ErrInvalidToken
	}

	claims, ok := token.Claims.(*domain.Claims)
	if !ok || !token.Valid {
		return nil, domain.ErrInvalidToken
	}

	return claims, nil
}
