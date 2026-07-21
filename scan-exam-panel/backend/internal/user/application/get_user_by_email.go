package application

import (
	"context"
	"scan-exam-api/internal/user/domain"
)

type GetUserByEmailRequest struct {
	Email string `json:"email"`
}

type GetUserByEmailResponse struct {
	ID       string `json:"id"`
	Username string `json:"username"`
	Email    string `json:"email"`
}

type GetUserByEmailUseCase struct {
	users domain.Repository
}

func NewGetUserByEmailUseCase(users domain.Repository) *GetUserByEmailUseCase {
	return &GetUserByEmailUseCase{users: users}
}

func (uc *GetUserByEmailUseCase) Execute(ctx context.Context, req *GetUserByEmailRequest) (*GetUserByEmailResponse, error) {
	user, err := uc.users.GetByEmail(ctx, req.Email)
	if err != nil {
		return nil, err
	}

	return &GetUserByEmailResponse{
		ID:       user.ID,
		Username: user.Username,
		Email:    user.Email,
	}, nil
}
