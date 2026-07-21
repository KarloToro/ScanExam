package mongodb

import (
	"context"

	"scan-exam-api/internal/exam/domain"

	"go.mongodb.org/mongo-driver/v2/mongo"
)

type BatchRepository struct {
	col *mongo.Collection
}

func NewBatchRepository(db *mongo.Database) domain.BatchRepository {
	return &BatchRepository{col: db.Collection("batches")}
}

func (r *BatchRepository) Create(ctx context.Context, batch *domain.Batch) error {
	doc := batchFromDomain(batch)
	_, err := r.col.InsertOne(ctx, doc)
	if err != nil {
		return err
	}
	batch.ID = doc.ID
	batch.CreatedAt = doc.CreatedAt
	return nil
}
