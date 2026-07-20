package application

import (
	"context"
	"fmt"
	"path/filepath"
	"strings"

	"scan-exam-api/internal/exam/domain"
)

// DefaultN8NPort is the n8n HTTP port used when building the webhook URL.
const DefaultN8NPort = 5678

// DefaultN8NWebhookURL is the webhook endpoint inside the Docker network.
var DefaultN8NWebhookURL = fmt.Sprintf("http://n8n:%d/webhook/scanexam", DefaultN8NPort)

var supportedImageExt = map[string]struct{}{
	".jpg":  {},
	".jpeg": {},
	".png":  {},
}

type UploadExamRequest struct {
	Name     string
	Images   []domain.UploadedFile
	Students domain.UploadedFile
	Answers  domain.UploadedFile
}

type UploadExamResponse struct {
	OK      bool   `json:"ok"`
	BatchID string `json:"batch_id,omitempty"`
	Message string `json:"message,omitempty"`
}

type UploadExamUseCase struct {
	storage  domain.BatchStorage
	pipeline domain.PipelineClient
}

func NewUploadExamUseCase(storage domain.BatchStorage, pipeline domain.PipelineClient) *UploadExamUseCase {
	return &UploadExamUseCase{
		storage:  storage,
		pipeline: pipeline,
	}
}

func (uc *UploadExamUseCase) Execute(ctx context.Context, req *UploadExamRequest) (*UploadExamResponse, error) {
	if err := validateUpload(req); err != nil {
		return nil, err
	}

	written, err := uc.storage.Write(ctx, &domain.BatchWriteInput{
		Name:     strings.TrimSpace(req.Name),
		Images:   req.Images,
		Students: req.Students,
		Answers:  req.Answers,
	})
	if err != nil {
		return nil, err
	}

	if err := uc.pipeline.Trigger(ctx, written.BatchID, written.SourceRel); err != nil {
		return nil, err
	}

	return &UploadExamResponse{
		OK:      true,
		BatchID: written.BatchID,
		Message: "Package submitted to the pipeline successfully.",
	}, nil
}

func validateUpload(req *UploadExamRequest) error {
	if req == nil || strings.TrimSpace(req.Name) == "" {
		return domain.NewValidationError(domain.ErrNameRequired.Error())
	}

	validImages := make([]domain.UploadedFile, 0, len(req.Images))
	for _, img := range req.Images {
		ext := strings.ToLower(filepath.Ext(img.Filename))
		if _, ok := supportedImageExt[ext]; !ok {
			return domain.NewValidationError(domain.ErrInvalidImage.Error())
		}
		if len(img.Content) == 0 {
			continue
		}
		validImages = append(validImages, img)
	}
	if len(validImages) == 0 {
		return domain.NewValidationError(domain.ErrImagesRequired.Error())
	}
	req.Images = validImages

	if len(req.Students.Content) == 0 {
		return domain.NewValidationError(domain.ErrStudentsRequired.Error())
	}
	if !isCSVFilename(req.Students.Filename) {
		return domain.NewValidationError(domain.ErrInvalidStudentsCSV.Error())
	}

	if len(req.Answers.Content) == 0 {
		return domain.NewValidationError(domain.ErrAnswersRequired.Error())
	}
	if !isCSVFilename(req.Answers.Filename) {
		return domain.NewValidationError(domain.ErrInvalidAnswersCSV.Error())
	}

	return nil
}

func isCSVFilename(name string) bool {
	return strings.EqualFold(filepath.Ext(name), ".csv")
}
