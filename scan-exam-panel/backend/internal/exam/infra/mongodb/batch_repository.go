package mongodb

import (
	"context"
	"errors"

	"scan-exam-api/internal/exam/domain"

	"go.mongodb.org/mongo-driver/v2/bson"
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

func (r *BatchRepository) GetByID(ctx context.Context, id string) (*domain.Batch, error) {
	doc := &batchDocument{}
	err := r.col.FindOne(ctx, bson.M{"_id": id}).Decode(doc)
	if err != nil {
		if errors.Is(err, mongo.ErrNoDocuments) {
			return nil, domain.ErrBatchNotFound
		}
		return nil, err
	}
	return doc.toDomain(), nil
}
