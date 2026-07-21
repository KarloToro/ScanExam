package middleware

import (
	"context"
	"net/http"
	"strings"

	"scan-exam-api/internal/auth/domain"
)

type contextKey string

const claimsContextKey contextKey = "auth_claims"

func JWTAuth(verifier domain.TokenVerifier) func(http.Handler) http.Handler {
	return func(next http.Handler) http.Handler {
		return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
			header := r.Header.Get("Authorization")
			if header == "" {
				http.Error(w, "missing authorization header", http.StatusUnauthorized)
				return
			}

			parts := strings.SplitN(header, " ", 2)
			if len(parts) != 2 || !strings.EqualFold(parts[0], "Bearer") || parts[1] == "" {
				http.Error(w, "invalid authorization header", http.StatusUnauthorized)
				return
			}

			claims, err := verifier.Verify(parts[1])
			if err != nil {
				http.Error(w, domain.ErrInvalidToken.Error(), http.StatusUnauthorized)
				return
			}

			ctx := context.WithValue(r.Context(), claimsContextKey, claims)
			next.ServeHTTP(w, r.WithContext(ctx))
		})
	}
}

func ClaimsFromContext(ctx context.Context) (*domain.Claims, bool) {
	claims, ok := ctx.Value(claimsContextKey).(*domain.Claims)
	return claims, ok
}

func UserIDFromContext(ctx context.Context) (string, bool) {
	claims, ok := ClaimsFromContext(ctx)
	if !ok || claims.Subject == "" {
		return "", false
	}
	return claims.Subject, true
}
