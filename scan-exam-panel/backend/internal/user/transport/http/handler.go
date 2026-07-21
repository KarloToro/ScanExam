package http

import (
	"encoding/json"
	"net/http"
	"scan-exam-api/internal/user/application"
	"scan-exam-api/internal/user/domain"
)

type UserHandler struct {
	createUserUseCase     *application.CreateUserUseCase
	getUserByEmailUseCase *application.GetUserByEmailUseCase
	getUserByIDUseCase    *application.GetUserByIDUseCase
	updateUserUseCase     *application.UpdateUserUseCase
	deleteUserUseCase     *application.DeleteUserUseCase
}

func NewUserHandler(
	users domain.Repository,
) *UserHandler {
	return &UserHandler{
		createUserUseCase:     application.NewCreateUserUseCase(users),
		getUserByEmailUseCase: application.NewGetUserByEmailUseCase(users),
		getUserByIDUseCase:    application.NewGetUserByIDUseCase(users),
		updateUserUseCase:     application.NewUpdateUserUseCase(users),
		deleteUserUseCase:     application.NewDeleteUserUseCase(users),
	}
}

func (h *UserHandler) CreateUser(w http.ResponseWriter, r *http.Request) {
	createUserRequest := &application.CreateUserRequest{}
	err := json.NewDecoder(r.Body).Decode(createUserRequest)
	if err != nil {
		http.Error(w, err.Error(), http.StatusBadRequest)
		return
	}

	createUserResponse, err := h.createUserUseCase.Execute(r.Context(), createUserRequest)
	if err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}

	w.WriteHeader(http.StatusCreated)
	json.NewEncoder(w).Encode(createUserResponse)
}

func (h *UserHandler) GetUserByEmail(w http.ResponseWriter, r *http.Request) {
	email := r.URL.Query().Get("email")
	if email == "" {
		http.Error(w, "Email is required", http.StatusBadRequest)
		return
	}

	getUserByEmailRequest := &application.GetUserByEmailRequest{
		Email: email,
	}

	getUserByEmailResponse, err := h.getUserByEmailUseCase.Execute(r.Context(), getUserByEmailRequest)
	if err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}

	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(getUserByEmailResponse)
}

func (h *UserHandler) GetUserByID(w http.ResponseWriter, r *http.Request) {
	id := r.URL.Query().Get("id")
	if id == "" {
		http.Error(w, "ID is required", http.StatusBadRequest)
		return
	}

	getUserByIDRequest := &application.GetUserByIDRequest{
		ID: id,
	}

	getUserByIDResponse, err := h.getUserByIDUseCase.Execute(r.Context(), getUserByIDRequest)
	if err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}

	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(getUserByIDResponse)
}

func (h *UserHandler) UpdateUser(w http.ResponseWriter, r *http.Request) {
	updateUserRequest := &application.UpdateUserRequest{}
	err := json.NewDecoder(r.Body).Decode(updateUserRequest)
	if err != nil {
		http.Error(w, err.Error(), http.StatusBadRequest)
		return
	}

	updateUserResponse, err := h.updateUserUseCase.Execute(r.Context(), updateUserRequest)
	if err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}

	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(updateUserResponse)
}

func (h *UserHandler) DeleteUser(w http.ResponseWriter, r *http.Request) {
	id := r.URL.Query().Get("id")
	if id == "" {
		http.Error(w, "ID is required", http.StatusBadRequest)
		return
	}

	deleteUserRequest := &application.DeleteUserRequest{
		ID: id,
	}

	err := h.deleteUserUseCase.Execute(r.Context(), deleteUserRequest)
	if err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}

	w.WriteHeader(http.StatusNoContent)
}
