package mongodb

import (
	"scan-exam-api/internal/user/domain"

	"go.mongodb.org/mongo-driver/v2/bson"
)

type UserDocument struct {
	ID       string `bson:"_id"`
	Username string `bson:"username"`
	Email    string `bson:"email"`
	Password string `bson:"password"`
}

func (document *UserDocument) ToDomain() *domain.User {
	return &domain.User{
		ID:       document.ID,
		Username: document.Username,
		Email:    document.Email,
		Password: document.Password,
	}
}

func (document *UserDocument) FromDomain(user *domain.User) {
	document.ID = user.ID
	document.Username = user.Username
	document.Email = user.Email
	document.Password = user.Password

	if user.ID == "" {
		document.ID = bson.NewObjectID().Hex()
	}
}
