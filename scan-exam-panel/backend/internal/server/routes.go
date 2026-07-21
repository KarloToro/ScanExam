package server

import (
	"net/http"

	authhttp "scan-exam-api/internal/auth/transport/http"
	examhttp "scan-exam-api/internal/exam/transport/http"
	appmiddleware "scan-exam-api/internal/middleware"
	userhttp "scan-exam-api/internal/user/transport/http"

	"github.com/go-chi/chi/v5"
	"github.com/go-chi/chi/v5/middleware"
	"github.com/go-chi/cors"
)

func (s *Server) RegisterRoutes() http.Handler {
	r := chi.NewRouter()
	r.Use(middleware.Logger)

	r.Use(cors.Handler(cors.Options{
		AllowedOrigins:   []string{"https://*", "http://*"},
		AllowedMethods:   []string{"GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"},
		AllowedHeaders:   []string{"Accept", "Authorization", "Content-Type"},
		AllowCredentials: true,
		MaxAge:           300,
	}))

	r.Mount("/auth", authhttp.AuthRouter(s.authHandler))
	r.Mount("/results", examhttp.ResultRouter(s.resultHandler))

	r.Group(func(r chi.Router) {
		r.Use(appmiddleware.JWTAuth(s.jwtService))
		r.Mount("/users", userhttp.UserRouter(s.userHandler))
		r.Mount("/exams", examhttp.ExamRouter(s.examHandler))
	})

	return r
}
