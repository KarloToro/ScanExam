package application

import (
	"context"
	"strings"

	"scan-exam-api/internal/exam/domain"
)

type LookupResultRequest struct {
	ID        string `json:"id"`
	AccessKey string `json:"access_key"`
}

type LookupAnswerDTO struct {
	QuestionID     int     `json:"question_id"`
	DetectedAnswer any     `json:"detected_answer"`
	CorrectAnswer  string  `json:"correct_answer"`
	QuestionStatus string  `json:"question_status"`
	Points         float64 `json:"points"`
	EarnedPoints   float64 `json:"earned_points"`
}

type LookupResultResponse struct {
	ExamName    string            `json:"exam_name"`
	StudentName string            `json:"student_name,omitempty"`
	Score       *float64          `json:"score"`
	MaxScore    *float64          `json:"max_score"`
	Percentage  *float64          `json:"percentage"`
	Answers     []LookupAnswerDTO `json:"answers"`
}

type LookupResultUseCase struct {
	results domain.ResultRepository
	batches domain.BatchRepository
}

func NewLookupResultUseCase(
	results domain.ResultRepository,
	batches domain.BatchRepository,
) *LookupResultUseCase {
	return &LookupResultUseCase{
		results: results,
		batches: batches,
	}
}

func (uc *LookupResultUseCase) Execute(ctx context.Context, req *LookupResultRequest) (*LookupResultResponse, error) {
	if req == nil {
		return nil, domain.ErrResultNotFound
	}
	id := strings.TrimSpace(req.ID)
	accessKey := strings.TrimSpace(req.AccessKey)
	if id == "" || accessKey == "" {
		return nil, domain.ErrResultNotFound
	}

	result, err := uc.results.FindByIDAndAccessKey(ctx, id, accessKey)
	if err != nil {
		return nil, err
	}
	if !result.IsPublishableGrade() {
		return nil, domain.ErrResultNotFound
	}

	batch, err := uc.batches.GetByID(ctx, result.BatchRef)
	if err != nil {
		return nil, err
	}

	studentName := ""
	if result.StudentName != nil {
		studentName = *result.StudentName
	}

	answers := make([]LookupAnswerDTO, 0, len(result.Answers))
	for _, a := range result.Answers {
		answers = append(answers, LookupAnswerDTO{
			QuestionID:     a.QuestionID,
			DetectedAnswer: a.DetectedAnswer,
			CorrectAnswer:  a.CorrectAnswer,
			QuestionStatus: a.QuestionStatus,
			Points:         a.Points,
			EarnedPoints:   a.EarnedPoints,
		})
	}

	return &LookupResultResponse{
		ExamName:    batch.Name,
		StudentName: studentName,
		Score:       result.Score,
		MaxScore:    result.MaxScore,
		Percentage:  result.Percentage,
		Answers:     answers,
	}, nil
}
