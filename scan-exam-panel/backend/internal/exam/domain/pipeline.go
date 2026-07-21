package domain

import "context"

type PipelineScorePayload struct {
	OK      bool                `json:"ok"`
	BatchID string              `json:"batch_id"`
	Summary StatusSummary       `json:"summary"`
	Bundle  PipelineScoreBundle `json:"resultados"`
}

type PipelineScoreBundle struct {
	BatchID     string                `json:"batch_id"`
	GeneratedBy string                `json:"generated_by"`
	Results     []PipelineSheetResult `json:"results"`
}

type PipelineSheetResult struct {
	File              string        `json:"file"`
	ProcessingStatus  string        `json:"processing_status"`
	QualityStatus     string        `json:"quality_status"`
	Publishable       bool          `json:"publishable"`
	StudentCode       StudentCode   `json:"student_code"`
	StudentName       *string       `json:"student_name"`
	Email             *string       `json:"email"`
	Score             *float64      `json:"score"`
	MaxScore          *float64      `json:"max_score"`
	Percentage        *float64      `json:"percentage"`
	IssueCode         *string       `json:"issue_code"`
	ProcessingMessage string        `json:"processing_message"`
	Answers           []AnswerGrade `json:"answers"`
}

type PipelineClient interface {
	Trigger(ctx context.Context, batchID, sourceRel string) (*PipelineScorePayload, error)
}
