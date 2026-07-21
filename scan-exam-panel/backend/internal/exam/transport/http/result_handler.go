package http

import (
	"encoding/json"
	"errors"
	"net/http"

	"scan-exam-api/internal/exam/application"
	"scan-exam-api/internal/exam/domain"
)

type ResultHandler struct {
	lookupResultUseCase *application.LookupResultUseCase
}

func NewResultHandler(lookupResultUseCase *application.LookupResultUseCase) *ResultHandler {
	return &ResultHandler{lookupResultUseCase: lookupResultUseCase}
}

func (h *ResultHandler) Lookup(w http.ResponseWriter, r *http.Request) {
	var req application.LookupResultRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		writeLookupError(w, http.StatusBadRequest, "invalid request body")
		return
	}

	resp, err := h.lookupResultUseCase.Execute(r.Context(), &req)
	if err != nil {
		if errors.Is(err, domain.ErrResultNotFound) || errors.Is(err, domain.ErrBatchNotFound) {
			writeLookupError(w, http.StatusNotFound, "clave inválida o resultado no disponible")
			return
		}
		writeLookupError(w, http.StatusInternalServerError, "failed to look up result")
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	_ = json.NewEncoder(w).Encode(resp)
}

func writeLookupError(w http.ResponseWriter, status int, message string) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	_ = json.NewEncoder(w).Encode(map[string]string{"message": message})
}
