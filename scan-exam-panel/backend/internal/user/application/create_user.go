package application

import (
	"context"
	"scan-exam-api/internal/user/domain"

	"golang.org/x/crypto/bcrypt"
)

type CreateUserRequest struct {
	Username string `json:"username"`
	Email    string `json:"email"`
	Password string `json:"password"`
}

type CreateUserResponse struct {
	ID string `json:"id"`
}

type CreateUserUseCase struct {
	users domain.Repository
}

func NewCreateUserUseCase(users domain.Repository) *CreateUserUseCase {
	return &CreateUserUseCase{users: users}
}

func (uc *CreateUserUseCase) Execute(ctx context.Context, req *CreateUserRequest) (*CreateUserResponse, error) {
	hashedPassword, err := bcrypt.GenerateFromPassword([]byte(req.Password), bcrypt.DefaultCost)
	if err != nil {
		return nil, err
	}

	user := &domain.User{
		Username: req.Username,
		Email:    req.Email,
		Password: string(hashedPassword),
	}

	err = uc.users.Create(ctx, user)
	if err != nil {
		return nil, err
	}

	return &CreateUserResponse{
		ID: user.ID,
	}, nil
}
