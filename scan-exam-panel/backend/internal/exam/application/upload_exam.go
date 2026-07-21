package application

import (
	"context"
	"fmt"
	"path/filepath"
	"strings"

	"scan-exam-api/internal/exam/domain"
	"scan-exam-api/internal/notification"
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
	batches  domain.BatchRepository
	results  domain.ResultRepository
	notifier notification.Notifier
}

func NewUploadExamUseCase(
	storage domain.BatchStorage,
	pipeline domain.PipelineClient,
	batches domain.BatchRepository,
	results domain.ResultRepository,
	notifier notification.Notifier,
) *UploadExamUseCase {
	return &UploadExamUseCase{
		storage:  storage,
		pipeline: pipeline,
		batches:  batches,
		results:  results,
		notifier: notifier,
	}
}

func (uc *UploadExamUseCase) Execute(ctx context.Context, req *UploadExamRequest) (*UploadExamResponse, error) {
	if err := validateUpload(req); err != nil {
		return nil, err
	}

	examName := strings.TrimSpace(req.Name)

	written, err := uc.storage.Write(ctx, &domain.BatchWriteInput{
		Name:     examName,
		Images:   req.Images,
		Students: req.Students,
		Answers:  req.Answers,
	})
	if err != nil {
		return nil, err
	}

	payload, err := uc.pipeline.Trigger(ctx, written.BatchID, written.SourceRel)
	if err != nil {
		return nil, err
	}

	batch := &domain.Batch{
		BatchID: written.BatchID,
		Name:    examName,
		Summary: payload.Summary,
	}
	if err := uc.batches.Create(ctx, batch); err != nil {
		return nil, fmt.Errorf("%w: batch: %v", domain.ErrPersistFailed, err)
	}

	persisted := make([]*domain.Result, 0, len(payload.Bundle.Results))
	for _, sheet := range payload.Bundle.Results {
		persisted = append(persisted, sheetResultToDomain(sheet, batch.ID))
	}
	if err := uc.results.CreateMany(ctx, persisted); err != nil {
		return nil, fmt.Errorf("%w: results: %v", domain.ErrPersistFailed, err)
	}

	if err := uc.notifier.Send(ctx, gradeMessages(examName, persisted)); err != nil {
		return nil, fmt.Errorf("%w: notify: %v", domain.ErrPersistFailed, err)
	}

	return &UploadExamResponse{
		OK:      true,
		BatchID: written.BatchID,
		Message: "Package submitted to the pipeline successfully.",
	}, nil
}

func gradeMessages(examName string, results []*domain.Result) []notification.Message {
	messages := make([]notification.Message, 0)
	for _, result := range results {
		if !result.IsPublishableGrade() {
			continue
		}
		if result.Email == nil || strings.TrimSpace(*result.Email) == "" {
			continue
		}

		score := 0.0
		maxScore := 0.0
		percentage := 0.0
		if result.Score != nil {
			score = *result.Score
		}
		if result.MaxScore != nil {
			maxScore = *result.MaxScore
		}
		if result.Percentage != nil {
			percentage = *result.Percentage
		}

		studentName := ""
		if result.StudentName != nil {
			studentName = *result.StudentName
		}

		messages = append(messages, notification.Message{
			To:      strings.TrimSpace(*result.Email),
			Subject: fmt.Sprintf("Nota disponible: %s", examName),
			Body: fmt.Sprintf(
				"Hola %s,\n\nTu nota en \"%s\" es %.2f / %.2f (%.2f%%).\n",
				studentName, examName, score, maxScore, percentage,
			),
		})
	}
	return messages
}

func sheetResultToDomain(sheet domain.PipelineSheetResult, batchRef string) *domain.Result {
	answers := make([]domain.AnswerGrade, len(sheet.Answers))
	copy(answers, sheet.Answers)

	return &domain.Result{
		BatchRef:          batchRef,
		File:              sheet.File,
		ProcessingStatus:  sheet.ProcessingStatus,
		QualityStatus:     sheet.QualityStatus,
		Publishable:       sheet.Publishable,
		StudentCode:       sheet.StudentCode,
		StudentName:       sheet.StudentName,
		Email:             sheet.Email,
		Score:             sheet.Score,
		MaxScore:          sheet.MaxScore,
		Percentage:        sheet.Percentage,
		IssueCode:         sheet.IssueCode,
		ProcessingMessage: sheet.ProcessingMessage,
		Answers:           answers,
	}
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
