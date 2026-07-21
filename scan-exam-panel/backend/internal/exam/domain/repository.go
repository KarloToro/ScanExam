package domain

import "context"

type BatchRepository interface {
	Create(ctx context.Context, batch *Batch) error
}

type ResultRepository interface {
	CreateMany(ctx context.Context, results []*Result) error
}
