package mongodb

import (
	"context"
	"errors"
	"log"

	"scan-exam-api/internal/exam/domain"

	"go.mongodb.org/mongo-driver/v2/bson"
	"go.mongodb.org/mongo-driver/v2/mongo"
	"go.mongodb.org/mongo-driver/v2/mongo/options"
)

type ResultRepository struct {
	col *mongo.Collection
}

func NewResultRepository(db *mongo.Database) domain.ResultRepository {
	col := db.Collection("results")
	repo := &ResultRepository{col: col}
	repo.ensureIndexes(context.Background())
	return repo
}

func (r *ResultRepository) ensureIndexes(ctx context.Context) {
	_, err := r.col.Indexes().CreateOne(ctx, mongo.IndexModel{
		Keys:    bson.D{{Key: "access_key", Value: 1}},
		Options: options.Index().SetUnique(true),
	})
	if err != nil {
		log.Printf("failed to ensure results.access_key index: %v", err)
	}
}

func (r *ResultRepository) CreateMany(ctx context.Context, results []*domain.Result) error {
	if len(results) == 0 {
		return nil
	}

	docs := make([]any, 0, len(results))
	for _, result := range results {
		doc := resultFromDomain(result)
		docs = append(docs, doc)
		result.ID = doc.ID
		result.CreatedAt = doc.CreatedAt
	}

	_, err := r.col.InsertMany(ctx, docs)
	return err
}

func (r *ResultRepository) FindByIDAndAccessKey(ctx context.Context, id, accessKey string) (*domain.Result, error) {
	doc := &resultDocument{}
	err := r.col.FindOne(ctx, bson.M{
		"_id":        id,
		"access_key": accessKey,
	}).Decode(doc)
	if err != nil {
		if errors.Is(err, mongo.ErrNoDocuments) {
			return nil, domain.ErrResultNotFound
		}
		return nil, err
	}
	return doc.toDomain(), nil
}
