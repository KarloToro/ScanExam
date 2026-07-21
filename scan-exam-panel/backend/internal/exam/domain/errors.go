package domain

import "errors"

var (
	ErrNameRequired       = errors.New("exam name is required")
	ErrImagesRequired     = errors.New("at least one valid image is required (.jpg, .jpeg, .png)")
	ErrStudentsRequired   = errors.New("students CSV is required")
	ErrAnswersRequired    = errors.New("answers CSV is required")
	ErrInvalidImage       = errors.New("one or more images have an invalid extension")
	ErrInvalidStudentsCSV = errors.New("students file must be a CSV")
	ErrInvalidAnswersCSV  = errors.New("answers file must be a CSV")
	ErrPipelineFailed     = errors.New("pipeline failed")
	ErrPersistFailed      = errors.New("failed to persist exam results")
	ErrResultNotFound     = errors.New("result not found")
	ErrBatchNotFound      = errors.New("batch not found")
)

// ValidationError wraps a fail-fast validation message for the upload flow.
type ValidationError struct {
	Msg string
}

func (e *ValidationError) Error() string {
	return e.Msg
}

func NewValidationError(msg string) *ValidationError {
	return &ValidationError{Msg: msg}
}

func IsValidationError(err error) bool {
	var ve *ValidationError
	return errors.As(err, &ve)
}
