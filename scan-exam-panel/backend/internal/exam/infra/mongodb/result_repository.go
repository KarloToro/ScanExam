package mongodb

import (
	"context"

	"scan-exam-api/internal/exam/domain"

	"go.mongodb.org/mongo-driver/v2/mongo"
)

type ResultRepository struct {
	col *mongo.Collection
}

func NewResultRepository(db *mongo.Database) domain.ResultRepository {
	return &ResultRepository{col: db.Collection("results")}
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
