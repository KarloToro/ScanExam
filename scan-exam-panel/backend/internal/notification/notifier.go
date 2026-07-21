package notification

import "context"

type Message struct {
	To      string
	Subject string
	Body    string
}

type Notifier interface {
	Send(ctx context.Context, messages []Message) error
}
