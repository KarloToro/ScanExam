package mongodb

import (
	"time"

	"scan-exam-api/internal/exam/domain"

	"go.mongodb.org/mongo-driver/v2/bson"
)

type studentCodeDocument struct {
	Value      *string  `bson:"value"`
	Confidence *float64 `bson:"confidence"`
}

type answerGradeDocument struct {
	QuestionID     int      `bson:"question_id"`
	DetectedAnswer any      `bson:"detected_answer"`
	AcceptedAnswer *string  `bson:"accepted_answer"`
	CorrectAnswer  string   `bson:"correct_answer"`
	QuestionStatus string   `bson:"question_status"`
	Points         float64  `bson:"points"`
	EarnedPoints   float64  `bson:"earned_points"`
	Confidence     *float64 `bson:"confidence"`
}

type resultDocument struct {
	ID                string                `bson:"_id"`
	BatchRef          string                `bson:"batch_ref"`
	File              string                `bson:"file"`
	ProcessingStatus  string                `bson:"processing_status"`
	QualityStatus     string                `bson:"quality_status"`
	Publishable       bool                  `bson:"publishable"`
	StudentCode       studentCodeDocument   `bson:"student_code"`
	StudentName       *string               `bson:"student_name"`
	Email             *string               `bson:"email"`
	Score             *float64              `bson:"score"`
	MaxScore          *float64              `bson:"max_score"`
	Percentage        *float64              `bson:"percentage"`
	IssueCode         *string               `bson:"issue_code"`
	ProcessingMessage string                `bson:"processing_message"`
	Answers           []answerGradeDocument `bson:"answers"`
	CreatedAt         int64                 `bson:"created_at"`
}

func resultFromDomain(result *domain.Result) *resultDocument {
	answers := make([]answerGradeDocument, 0, len(result.Answers))
	for _, a := range result.Answers {
		answers = append(answers, answerGradeDocument{
			QuestionID:     a.QuestionID,
			DetectedAnswer: a.DetectedAnswer,
			AcceptedAnswer: a.AcceptedAnswer,
			CorrectAnswer:  a.CorrectAnswer,
			QuestionStatus: a.QuestionStatus,
			Points:         a.Points,
			EarnedPoints:   a.EarnedPoints,
			Confidence:     a.Confidence,
		})
	}

	doc := &resultDocument{
		ID:               result.ID,
		BatchRef:         result.BatchRef,
		File:             result.File,
		ProcessingStatus: result.ProcessingStatus,
		QualityStatus:    result.QualityStatus,
		Publishable:      result.Publishable,
		StudentCode: studentCodeDocument{
			Value:      result.StudentCode.Value,
			Confidence: result.StudentCode.Confidence,
		},
		StudentName:       result.StudentName,
		Email:             result.Email,
		Score:             result.Score,
		MaxScore:          result.MaxScore,
		Percentage:        result.Percentage,
		IssueCode:         result.IssueCode,
		ProcessingMessage: result.ProcessingMessage,
		Answers:           answers,
		CreatedAt:         result.CreatedAt,
	}
	if doc.ID == "" {
		doc.ID = bson.NewObjectID().Hex()
	}
	if doc.CreatedAt == 0 {
		doc.CreatedAt = time.Now().Unix()
	}
	if doc.Answers == nil {
		doc.Answers = []answerGradeDocument{}
	}
	return doc
}

func (doc *resultDocument) toDomain() *domain.Result {
	answers := make([]domain.AnswerGrade, 0, len(doc.Answers))
	for _, a := range doc.Answers {
		answers = append(answers, domain.AnswerGrade{
			QuestionID:     a.QuestionID,
			DetectedAnswer: a.DetectedAnswer,
			AcceptedAnswer: a.AcceptedAnswer,
			CorrectAnswer:  a.CorrectAnswer,
			QuestionStatus: a.QuestionStatus,
			Points:         a.Points,
			EarnedPoints:   a.EarnedPoints,
			Confidence:     a.Confidence,
		})
	}

	return &domain.Result{
		ID:               doc.ID,
		BatchRef:         doc.BatchRef,
		File:             doc.File,
		ProcessingStatus: doc.ProcessingStatus,
		QualityStatus:    doc.QualityStatus,
		Publishable:      doc.Publishable,
		StudentCode: domain.StudentCode{
			Value:      doc.StudentCode.Value,
			Confidence: doc.StudentCode.Confidence,
		},
		StudentName:       doc.StudentName,
		Email:             doc.Email,
		Score:             doc.Score,
		MaxScore:          doc.MaxScore,
		Percentage:        doc.Percentage,
		IssueCode:         doc.IssueCode,
		ProcessingMessage: doc.ProcessingMessage,
		Answers:           answers,
		CreatedAt:         doc.CreatedAt,
	}
}
