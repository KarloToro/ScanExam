package notification

import "context"

type Noop struct{}

func NewNoop() *Noop {
	return &Noop{}
}

func (n *Noop) Send(_ context.Context, _ []Message) error {
	return nil
}
