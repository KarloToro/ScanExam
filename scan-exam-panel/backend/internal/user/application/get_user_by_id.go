package application

import (
	"context"
	"scan-exam-api/internal/user/domain"
)

type GetUserByIDRequest struct {
	ID string `json:"id"`
}

type GetUserByIDResponse struct {
	ID       string `json:"id"`
	Username string `json:"username"`
	Email    string `json:"email"`
}

type GetUserByIDUseCase struct {
	users domain.Repository
}

func NewGetUserByIDUseCase(users domain.Repository) *GetUserByIDUseCase {
	return &GetUserByIDUseCase{users: users}
}

func (uc *GetUserByIDUseCase) Execute(ctx context.Context, req *GetUserByIDRequest) (*GetUserByIDResponse, error) {
	user, err := uc.users.GetByID(ctx, req.ID)
	if err != nil {
		return nil, err
	}

	return &GetUserByIDResponse{
		ID:       user.ID,
		Username: user.Username,
		Email:    user.Email,
	}, nil
}
