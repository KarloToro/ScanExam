package http

import "github.com/go-chi/chi/v5"

func ExamRouter(h *ExamHandler) *chi.Mux {
	r := chi.NewRouter()
	r.Post("/upload", h.Upload)
	return r
}
