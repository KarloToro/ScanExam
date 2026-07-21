package domain

import "context"

// UploadedFile is a file payload already read from the multipart request.
type UploadedFile struct {
	Filename string
	Content  []byte
}

// BatchWriteInput is the payload needed to materialize a processable batch on disk.
type BatchWriteInput struct {
	Name     string
	Images   []UploadedFile
	Students UploadedFile
	Answers  UploadedFile
}

// BatchWriteResult identifies the written batch and its source path relative to the workspace.
type BatchWriteResult struct {
	BatchID   string
	SourceRel string
}

// BatchStorage persists an exam upload into the Fichas/Estudiantes/Respuestas layout.
type BatchStorage interface {
	Write(ctx context.Context, input *BatchWriteInput) (*BatchWriteResult, error)
}
