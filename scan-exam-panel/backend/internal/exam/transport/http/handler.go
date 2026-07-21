package http

import (
	"encoding/json"
	"errors"
	"io"
	"net/http"
	"path/filepath"
	"strings"

	"scan-exam-api/internal/exam/application"
	"scan-exam-api/internal/exam/domain"
)

const maxMultipartMemory = 64 << 20 // 64 MiB

type ExamHandler struct {
	uploadExamUseCase *application.UploadExamUseCase
}

func NewExamHandler(uploadExamUseCase *application.UploadExamUseCase) *ExamHandler {
	return &ExamHandler{uploadExamUseCase: uploadExamUseCase}
}

func (h *ExamHandler) Upload(w http.ResponseWriter, r *http.Request) {
	if err := r.ParseMultipartForm(maxMultipartMemory); err != nil {
		writeJSON(w, http.StatusBadRequest, &application.UploadExamResponse{
			OK:      false,
			Message: "failed to parse multipart form",
		})
		return
	}

	name := strings.TrimSpace(r.FormValue("name"))

	images, err := readMultipartFiles(r, "images")
	if err != nil {
		writeJSON(w, http.StatusBadRequest, &application.UploadExamResponse{
			OK:      false,
			Message: "failed to read images",
		})
		return
	}

	students, err := readSingleMultipartFile(r, "students")
	if err != nil {
		writeJSON(w, http.StatusBadRequest, &application.UploadExamResponse{
			OK:      false,
			Message: domain.ErrStudentsRequired.Error(),
		})
		return
	}

	answers, err := readSingleMultipartFile(r, "answers")
	if err != nil {
		writeJSON(w, http.StatusBadRequest, &application.UploadExamResponse{
			OK:      false,
			Message: domain.ErrAnswersRequired.Error(),
		})
		return
	}

	resp, err := h.uploadExamUseCase.Execute(r.Context(), &application.UploadExamRequest{
		Name:     name,
		Images:   images,
		Students: students,
		Answers:  answers,
	})
	if err != nil {
		status := http.StatusInternalServerError
		message := err.Error()

		if domain.IsValidationError(err) {
			status = http.StatusBadRequest
		} else if errors.Is(err, domain.ErrPipelineFailed) {
			status = http.StatusBadGateway
			message = err.Error()
		} else if errors.Is(err, domain.ErrPersistFailed) {
			status = http.StatusInternalServerError
			message = err.Error()
		}

		writeJSON(w, status, &application.UploadExamResponse{
			OK:      false,
			Message: message,
		})
		return
	}

	writeJSON(w, http.StatusOK, resp)
}

func readMultipartFiles(r *http.Request, field string) ([]domain.UploadedFile, error) {
	if r.MultipartForm == nil {
		return nil, errors.New("multipart form not parsed")
	}

	headers := r.MultipartForm.File[field]
	files := make([]domain.UploadedFile, 0, len(headers))
	for _, header := range headers {
		f, err := header.Open()
		if err != nil {
			return nil, err
		}
		content, err := io.ReadAll(f)
		_ = f.Close()
		if err != nil {
			return nil, err
		}
		files = append(files, domain.UploadedFile{
			Filename: filepath.Base(header.Filename),
			Content:  content,
		})
	}
	return files, nil
}

func readSingleMultipartFile(r *http.Request, field string) (domain.UploadedFile, error) {
	file, header, err := r.FormFile(field)
	if err != nil {
		return domain.UploadedFile{}, err
	}
	defer file.Close()

	content, err := io.ReadAll(file)
	if err != nil {
		return domain.UploadedFile{}, err
	}

	return domain.UploadedFile{
		Filename: filepath.Base(header.Filename),
		Content:  content,
	}, nil
}

func writeJSON(w http.ResponseWriter, status int, payload *application.UploadExamResponse) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	_ = json.NewEncoder(w).Encode(payload)
}
