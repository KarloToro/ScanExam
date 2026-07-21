package domain

type StudentCode struct {
	Value      *string  `json:"value"`
	Confidence *float64 `json:"confidence"`
}

type AnswerGrade struct {
	QuestionID     int      `json:"question_id"`
	DetectedAnswer any      `json:"detected_answer"`
	AcceptedAnswer *string  `json:"accepted_answer"`
	CorrectAnswer  string   `json:"correct_answer"`
	QuestionStatus string   `json:"question_status"`
	Points         float64  `json:"points"`
	EarnedPoints   float64  `json:"earned_points"`
	Confidence     *float64 `json:"confidence"`
}

type Result struct {
	ID                string
	BatchRef          string
	AccessKey         string
	File              string
	ProcessingStatus  string
	QualityStatus     string
	Publishable       bool
	StudentCode       StudentCode
	StudentName       *string
	Email             *string
	Score             *float64
	MaxScore          *float64
	Percentage        *float64
	IssueCode         *string
	ProcessingMessage string
	Answers           []AnswerGrade
	CreatedAt         int64
}

func (r *Result) IsPublishableGrade() bool {
	return r.ProcessingStatus == "OK" && r.QualityStatus == "OK"
}
