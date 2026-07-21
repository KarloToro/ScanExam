package n8n

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"strings"
	"time"

	"scan-exam-api/internal/exam/domain"
)

const defaultTimeout = 300 * time.Second

type Client struct {
	webhookURL string
	httpClient *http.Client
}

func NewClient(webhookURL string) *Client {
	return &Client{
		webhookURL: webhookURL,
		httpClient: &http.Client{Timeout: defaultTimeout},
	}
}

type triggerPayload struct {
	BatchID string `json:"batch_id"`
	Source  string `json:"source"`
}

func (c *Client) Trigger(ctx context.Context, batchID, sourceRel string) (*domain.PipelineScorePayload, error) {
	body, err := json.Marshal(triggerPayload{
		BatchID: batchID,
		Source:  sourceRel,
	})
	if err != nil {
		return nil, fmt.Errorf("%w: %v", domain.ErrPipelineFailed, err)
	}

	req, err := http.NewRequestWithContext(ctx, http.MethodPost, c.webhookURL, bytes.NewReader(body))
	if err != nil {
		return nil, fmt.Errorf("%w: %v", domain.ErrPipelineFailed, err)
	}
	req.Header.Set("Content-Type", "application/json")

	resp, err := c.httpClient.Do(req)
	if err != nil {
		return nil, fmt.Errorf("%w: %v", domain.ErrPipelineFailed, err)
	}
	defer resp.Body.Close()

	respBody, err := io.ReadAll(io.LimitReader(resp.Body, 16<<20))
	if err != nil {
		return nil, fmt.Errorf("%w: read response: %v", domain.ErrPipelineFailed, err)
	}
	if resp.StatusCode < 200 || resp.StatusCode >= 300 {
		msg := strings.TrimSpace(string(respBody))
		if msg == "" {
			msg = resp.Status
		}
		return nil, fmt.Errorf("%w: %s", domain.ErrPipelineFailed, msg)
	}

	var payload domain.PipelineScorePayload
	if err := json.Unmarshal(respBody, &payload); err != nil {
		return nil, fmt.Errorf("%w: decode response: %v", domain.ErrPipelineFailed, err)
	}
	if !payload.OK {
		return nil, fmt.Errorf("%w: pipeline response ok=false", domain.ErrPipelineFailed)
	}

	return &payload, nil
}
