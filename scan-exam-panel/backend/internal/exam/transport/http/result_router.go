package http

import "github.com/go-chi/chi/v5"

func ResultRouter(h *ResultHandler) *chi.Mux {
	r := chi.NewRouter()
	r.Post("/lookup", h.Lookup)
	return r
}
