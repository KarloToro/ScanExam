package domain

import "context"

// PipelineClient triggers the ScanExam processing pipeline (n8n webhook).
type PipelineClient interface {
	Trigger(ctx context.Context, batchID, sourceRel string) error
}
