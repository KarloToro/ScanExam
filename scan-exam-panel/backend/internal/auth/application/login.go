package application

import (
	"context"
	"strings"

	"scan-exam-api/internal/auth/domain"
	userdomain "scan-exam-api/internal/user/domain"

	"golang.org/x/crypto/bcrypt"
)

type LoginRequest struct {
	Login    string `json:"login"`
	Password string `json:"password"`
}

type LoginResponse struct {
	Token     string `json:"token"`
	TokenType string `json:"token_type"`
	ExpiresIn int64  `json:"expires_in"`
}

type LoginUseCase struct {
	users userdomain.Repository
	jwt   *JWTService
}

func NewLoginUseCase(users userdomain.Repository, jwt *JWTService) *LoginUseCase {
	return &LoginUseCase{users: users, jwt: jwt}
}

func (uc *LoginUseCase) Execute(ctx context.Context, req *LoginRequest) (*LoginResponse, error) {
	login := strings.TrimSpace(req.Login)
	if login == "" || req.Password == "" {
		return nil, domain.ErrInvalidCredentials
	}

	var (
		user *userdomain.User
		err  error
	)

	if strings.Contains(login, "@") {
		user, err = uc.users.GetByEmail(ctx, login)
	} else {
		user, err = uc.users.GetByUsername(ctx, login)
	}
	if err != nil {
		return nil, domain.ErrInvalidCredentials
	}

	if err := bcrypt.CompareHashAndPassword([]byte(user.Password), []byte(req.Password)); err != nil {
		return nil, domain.ErrInvalidCredentials
	}

	token, err := uc.jwt.Sign(user.ID, user.Username, user.Email)
	if err != nil {
		return nil, err
	}

	return &LoginResponse{
		Token:     token,
		TokenType: "Bearer",
		ExpiresIn: int64(uc.jwt.TTL().Seconds()),
	}, nil
}
