package application

import (
	"context"
	"scan-exam-api/internal/user/domain"
)

type DeleteUserRequest struct {
	ID string `json:"id"`
}

type DeleteUserUseCase struct {
	users domain.Repository
}

func NewDeleteUserUseCase(users domain.Repository) *DeleteUserUseCase {
	return &DeleteUserUseCase{users: users}
}

func (uc *DeleteUserUseCase) Execute(ctx context.Context, req *DeleteUserRequest) error {
	return uc.users.Delete(ctx, req.ID)
}
