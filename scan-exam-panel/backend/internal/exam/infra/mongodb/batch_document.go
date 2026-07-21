package mongodb

import (
	"time"

	"scan-exam-api/internal/exam/domain"

	"go.mongodb.org/mongo-driver/v2/bson"
)

type batchDocument struct {
	ID        string               `bson:"_id"`
	BatchID   string               `bson:"batch_id"`
	Name      string               `bson:"name"`
	Summary   domain.StatusSummary `bson:"summary"`
	CreatedAt int64                `bson:"created_at"`
}

func batchFromDomain(batch *domain.Batch) *batchDocument {
	doc := &batchDocument{
		ID:        batch.ID,
		BatchID:   batch.BatchID,
		Name:      batch.Name,
		Summary:   batch.Summary,
		CreatedAt: batch.CreatedAt,
	}
	if doc.ID == "" {
		doc.ID = bson.NewObjectID().Hex()
	}
	if doc.CreatedAt == 0 {
		doc.CreatedAt = time.Now().Unix()
	}
	return doc
}

func (doc *batchDocument) toDomain() *domain.Batch {
	return &domain.Batch{
		ID:        doc.ID,
		BatchID:   doc.BatchID,
		Name:      doc.Name,
		Summary:   doc.Summary,
		CreatedAt: doc.CreatedAt,
	}
}
