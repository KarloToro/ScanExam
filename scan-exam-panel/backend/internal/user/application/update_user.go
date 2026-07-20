package application

import (
	"context"
	"scan-exam-api/internal/user/domain"
)

type UpdateUserRequest struct {
	ID       string `json:"id"`
	Username string `json:"username"`
	Email    string `json:"email"`
}

type UpdateUserResponse struct {
	ID string `json:"id"`
}

type UpdateUserUseCase struct {
	users domain.Repository
}

func NewUpdateUserUseCase(users domain.Repository) *UpdateUserUseCase {
	return &UpdateUserUseCase{users: users}
}

func (uc *UpdateUserUseCase) Execute(ctx context.Context, req *UpdateUserRequest) (*UpdateUserResponse, error) {
	user, err := uc.users.GetByID(ctx, req.ID)
	if err != nil {
		return nil, err
	}

	user.Username = req.Username
	user.Email = req.Email

	err = uc.users.Update(ctx, user)
	if err != nil {
		return nil, err
	}

	return &UpdateUserResponse{
		ID: user.ID,
	}, nil
}
