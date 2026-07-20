package http

import "github.com/go-chi/chi/v5"

func AuthRouter(h *AuthHandler) *chi.Mux {
	r := chi.NewRouter()
	r.Post("/login", h.Login)
	return r
}
