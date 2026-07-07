package ratelimit

import (
	"errors"
	"testing"
)

func TestLimiterErrorError(t *testing.T) {
	err := newError(ErrInvalidConfig, "capacity must be positive, got %d", -1)
	want := "INVALID_CONFIG: capacity must be positive, got -1"
	if got := err.Error(); got != want {
		t.Errorf("Error() = %q, want %q", got, want)
	}
}

func TestLimiterErrorAsCode(t *testing.T) {
	tests := []struct {
		name string
		err  error
		want ErrorCode
	}{
		{"invalid config", newError(ErrInvalidConfig, "x"), ErrInvalidConfig},
		{"unknown limiter", newError(ErrUnknownLimiter, "x"), ErrUnknownLimiter},
		{"duplicate limiter", newError(ErrDuplicateLimiter, "x"), ErrDuplicateLimiter},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			var le *LimiterError
			if !errors.As(tt.err, &le) {
				t.Fatalf("errors.As failed for %v", tt.err)
			}
			if le.Code != tt.want {
				t.Errorf("Code = %q, want %q", le.Code, tt.want)
			}
		})
	}
}
