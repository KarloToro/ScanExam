package mongodb

import (
	"context"
	"scan-exam-api/internal/user/domain"

	"go.mongodb.org/mongo-driver/v2/bson"
	"go.mongodb.org/mongo-driver/v2/mongo"
)

type UserRepository struct {
	db *mongo.Collection
}

func NewUserRepository(db *mongo.Database) domain.Repository {
	return &UserRepository{
		db: db.Collection("users"),
	}
}

func (r *UserRepository) Create(ctx context.Context, user *domain.User) error {
	document := &UserDocument{}
	document.FromDomain(user)

	_, err := r.db.InsertOne(ctx, document)
	if err != nil {
		return err
	}

	user.ID = document.ID
	return nil
}

func (r *UserRepository) GetByEmail(ctx context.Context, email string) (*domain.User, error) {
	document := &UserDocument{}
	err := r.db.FindOne(ctx, bson.M{"email": email}).Decode(document)
	if err != nil {
		return nil, err
	}

	return document.ToDomain(), nil
}

func (r *UserRepository) GetByUsername(ctx context.Context, username string) (*domain.User, error) {
	document := &UserDocument{}
	err := r.db.FindOne(ctx, bson.M{"username": username}).Decode(document)
	if err != nil {
		return nil, err
	}

	return document.ToDomain(), nil
}

func (r *UserRepository) GetByID(ctx context.Context, id string) (*domain.User, error) {
	document := &UserDocument{}
	err := r.db.FindOne(ctx, bson.M{"_id": id}).Decode(document)
	if err != nil {
		return nil, err
	}

	return document.ToDomain(), nil
}

func (r *UserRepository) Update(ctx context.Context, user *domain.User) error {
	document := &UserDocument{}
	document.FromDomain(user)

	_, err := r.db.UpdateOne(ctx, bson.M{"_id": document.ID}, bson.M{"$set": document})
	if err != nil {
		return err
	}

	return nil
}

func (r *UserRepository) Delete(ctx context.Context, id string) error {
	_, err := r.db.DeleteOne(ctx, bson.M{"_id": id})
	if err != nil {
		return err
	}

	return nil
}
