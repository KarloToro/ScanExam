package http

import "github.com/go-chi/chi/v5"

func UserRouter(h *UserHandler) *chi.Mux {
	r := chi.NewRouter()
	r.Post("/", h.CreateUser)
	r.Get("/", h.GetUserByEmail)
	r.Get("/{id}", h.GetUserByID)
	r.Put("/{id}", h.UpdateUser)
	r.Delete("/{id}", h.DeleteUser)
	return r
}
