package http

import (
	"encoding/json"
	"errors"
	"net/http"

	"scan-exam-api/internal/auth/application"
	"scan-exam-api/internal/auth/domain"
)

type AuthHandler struct {
	loginUseCase *application.LoginUseCase
}

func NewAuthHandler(loginUseCase *application.LoginUseCase) *AuthHandler {
	return &AuthHandler{loginUseCase: loginUseCase}
}

func (h *AuthHandler) Login(w http.ResponseWriter, r *http.Request) {
	loginRequest := &application.LoginRequest{}
	if err := json.NewDecoder(r.Body).Decode(loginRequest); err != nil {
		http.Error(w, err.Error(), http.StatusBadRequest)
		return
	}

	loginResponse, err := h.loginUseCase.Execute(r.Context(), loginRequest)
	if err != nil {
		if errors.Is(err, domain.ErrInvalidCredentials) {
			http.Error(w, domain.ErrInvalidCredentials.Error(), http.StatusUnauthorized)
			return
		}
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(loginResponse)
}
