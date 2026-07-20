package storage

import (
	"context"
	"fmt"
	"os"
	"path/filepath"
	"strings"
	"time"

	"scan-exam-api/internal/exam/domain"
)

// Directory names match the pipeline batch layout contract.
const (
	formsDir    = "Fichas"
	studentsDir = "Estudiantes"
	answersDir  = "Respuestas"
)

// BatchWriter writes exam uploads into the pipeline batch directory layout.
type BatchWriter struct {
	workspace  string
	uploadsDir string
}

func NewBatchWriter(workspace, uploadsDir string) *BatchWriter {
	if workspace == "" {
		workspace = "/workspace"
	}
	if uploadsDir == "" {
		uploadsDir = "uploads"
	}
	return &BatchWriter{
		workspace:  workspace,
		uploadsDir: uploadsDir,
	}
}

func (w *BatchWriter) Write(_ context.Context, input *domain.BatchWriteInput) (*domain.BatchWriteResult, error) {
	batchID := "BATCH-" + time.Now().Format("20060102-150405")
	dest := filepath.Join(w.workspace, w.uploadsDir, batchID)

	if err := os.MkdirAll(filepath.Join(dest, formsDir), 0o755); err != nil {
		return nil, fmt.Errorf("create %s directory: %w", formsDir, err)
	}
	if err := os.MkdirAll(filepath.Join(dest, studentsDir), 0o755); err != nil {
		return nil, fmt.Errorf("create %s directory: %w", studentsDir, err)
	}
	if err := os.MkdirAll(filepath.Join(dest, answersDir), 0o755); err != nil {
		return nil, fmt.Errorf("create %s directory: %w", answersDir, err)
	}

	for _, img := range input.Images {
		name := sanitizeFilename(img.Filename)
		path := filepath.Join(dest, formsDir, name)
		if err := os.WriteFile(path, img.Content, 0o644); err != nil {
			return nil, fmt.Errorf("save image %s: %w", name, err)
		}
	}

	studentsName := sanitizeFilename(input.Students.Filename)
	if studentsName == "" || !hasExt(studentsName, ".csv") {
		studentsName = "students.csv"
	}
	if err := os.WriteFile(
		filepath.Join(dest, studentsDir, studentsName),
		input.Students.Content,
		0o644,
	); err != nil {
		return nil, fmt.Errorf("save students CSV: %w", err)
	}

	answersName := sanitizeFilename(input.Answers.Filename)
	if answersName == "" || !hasExt(answersName, ".csv") {
		answersName = "answers.csv"
	}
	if err := os.WriteFile(
		filepath.Join(dest, answersDir, answersName),
		input.Answers.Content,
		0o644,
	); err != nil {
		return nil, fmt.Errorf("save answers CSV: %w", err)
	}

	sourceRel, err := filepath.Rel(w.workspace, dest)
	if err != nil {
		return nil, fmt.Errorf("batch relative path: %w", err)
	}

	return &domain.BatchWriteResult{
		BatchID:   batchID,
		SourceRel: filepath.ToSlash(sourceRel),
	}, nil
}

func sanitizeFilename(name string) string {
	name = filepath.Base(strings.TrimSpace(name))
	if name == "." || name == ".." {
		return ""
	}
	return name
}

func hasExt(name, ext string) bool {
	return strings.EqualFold(filepath.Ext(name), ext)
}
