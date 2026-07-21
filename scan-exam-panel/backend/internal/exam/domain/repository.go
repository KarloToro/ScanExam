package domain

import "context"

type BatchRepository interface {
	Create(ctx context.Context, batch *Batch) error
	GetByID(ctx context.Context, id string) (*Batch, error)
}

type ResultRepository interface {
	CreateMany(ctx context.Context, results []*Result) error
	FindByIDAndAccessKey(ctx context.Context, id, accessKey string) (*Result, error)
}
