package server

import (
	"context"
	"fmt"
	"log"
	"net/http"
	"os"
	"strconv"
	"time"

	_ "github.com/joho/godotenv/autoload"
	"go.mongodb.org/mongo-driver/v2/mongo"

	authapp "scan-exam-api/internal/auth/application"
	authhttp "scan-exam-api/internal/auth/transport/http"
	"scan-exam-api/internal/database"
	examapp "scan-exam-api/internal/exam/application"
	examn8n "scan-exam-api/internal/exam/infra/n8n"
	examstorage "scan-exam-api/internal/exam/infra/storage"
	examhttp "scan-exam-api/internal/exam/transport/http"
	userapp "scan-exam-api/internal/user/application"
	userdomain "scan-exam-api/internal/user/domain"
	usermongo "scan-exam-api/internal/user/infra/mongodb"
	userhttp "scan-exam-api/internal/user/transport/http"
)

type Server struct {
	port int
	*http.Server
	db          *mongo.Client
	jwtService  *authapp.JWTService
	userHandler *userhttp.UserHandler
	authHandler *authhttp.AuthHandler
	examHandler *examhttp.ExamHandler
}

func NewServer() *Server {
	port, _ := strconv.Atoi(os.Getenv("PORT"))

	jwtSecret := os.Getenv("JWT_SECRET")
	if jwtSecret == "" {
		log.Fatal("JWT_SECRET is required")
	}

	jwtExpiry := 24 * time.Hour
	if expiryStr := os.Getenv("JWT_EXPIRY"); expiryStr != "" {
		parsed, err := time.ParseDuration(expiryStr)
		if err != nil {
			log.Fatalf("invalid JWT_EXPIRY: %v", err)
		}
		jwtExpiry = parsed
	}

	myServer := &Server{
		port: port,
		db:   database.NewMongoClient(),
	}

	users := usermongo.NewUserRepository(myServer.db.Database("users"))
	jwtService := authapp.NewJWTService(jwtSecret, jwtExpiry)

	workspace := os.Getenv("SCANEXAM_WORKSPACE")
	uploadsDir := os.Getenv("SCANEXAM_UPLOADS_DIR")
	n8nWebhookURL := os.Getenv("N8N_WEBHOOK_URL")
	if n8nWebhookURL == "" {
		n8nWebhookURL = examapp.DefaultN8NWebhookURL
	}

	batchWriter := examstorage.NewBatchWriter(workspace, uploadsDir)
	pipelineClient := examn8n.NewClient(n8nWebhookURL)
	uploadExam := examapp.NewUploadExamUseCase(batchWriter, pipelineClient)

	myServer.jwtService = jwtService
	myServer.userHandler = userhttp.NewUserHandler(users)
	myServer.authHandler = authhttp.NewAuthHandler(authapp.NewLoginUseCase(users, jwtService))
	myServer.examHandler = examhttp.NewExamHandler(uploadExam)

	myServer.seedAdmin(users)

	httpServer := &http.Server{
		Addr:         fmt.Sprintf(":%d", myServer.port),
		Handler:      myServer.RegisterRoutes(),
		IdleTimeout:  time.Minute,
		ReadTimeout:  5 * time.Minute,
		WriteTimeout: 6 * time.Minute,
	}

	myServer.Server = httpServer

	return myServer
}

func (s *Server) Shutdown(ctx context.Context) error {
	return s.Server.Shutdown(ctx)
}

func (s *Server) seedAdmin(users userdomain.Repository) {
	ctx := context.Background()

	_, err := users.GetByUsername(ctx, "admin")
	if err == nil {
		log.Println("admin user already exists")
		return
	}

	password := os.Getenv("ADMIN_PASSWORD")
	if password == "" {
		log.Println("ADMIN_PASSWORD not set, skipping admin seed")
		return
	}

	email := os.Getenv("ADMIN_EMAIL")
	if email == "" {
		email = "admin@localhost"
	}

	createUser := userapp.NewCreateUserUseCase(users)
	_, err = createUser.Execute(ctx, &userapp.CreateUserRequest{
		Username: "admin",
		Email:    email,
		Password: password,
	})
	if err != nil {
		log.Printf("failed to seed admin user: %v", err)
		return
	}

	log.Println("admin user created")
}
