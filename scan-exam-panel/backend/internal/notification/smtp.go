package notification

import (
	"context"
	"fmt"
	"net"
	"net/mail"
	"net/smtp"
	"strings"
)

type SMTP struct {
	addr string
	from string
}

func NewSMTP(host, port, from string) *SMTP {
	host = strings.TrimSpace(host)
	port = strings.TrimSpace(port)
	if port == "" {
		port = "1025"
	}
	from = strings.TrimSpace(from)
	if from == "" {
		from = "ScanExam <noreply@scanexam.local>"
	}
	return &SMTP{
		addr: net.JoinHostPort(host, port),
		from: from,
	}
}

func (s *SMTP) Send(_ context.Context, messages []Message) error {
	fromAddr, err := parseAddress(s.from)
	if err != nil {
		return fmt.Errorf("smtp from: %w", err)
	}

	for _, message := range messages {
		toAddr, err := parseAddress(message.To)
		if err != nil {
			return fmt.Errorf("smtp to: %w", err)
		}

		body := buildMessage(s.from, message.To, message.Subject, message.Body)
		if err := smtp.SendMail(s.addr, nil, fromAddr, []string{toAddr}, body); err != nil {
			return fmt.Errorf("smtp send: %w", err)
		}
	}
	return nil
}

func parseAddress(value string) (string, error) {
	addr, err := mail.ParseAddress(value)
	if err != nil {
		return "", err
	}
	return addr.Address, nil
}

func buildMessage(from, to, subject, body string) []byte {
	var b strings.Builder
	b.WriteString("From: ")
	b.WriteString(from)
	b.WriteString("\r\n")
	b.WriteString("To: ")
	b.WriteString(to)
	b.WriteString("\r\n")
	b.WriteString("Subject: ")
	b.WriteString(subject)
	b.WriteString("\r\n")
	b.WriteString("MIME-Version: 1.0\r\n")
	b.WriteString("Content-Type: text/plain; charset=UTF-8\r\n")
	b.WriteString("\r\n")
	b.WriteString(body)
	return []byte(b.String())
}
