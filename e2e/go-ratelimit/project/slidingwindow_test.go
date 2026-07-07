package ratelimit

import (
	"errors"
	"testing"
	"time"
)

func TestNewSlidingWindowInvalidConfig(t *testing.T) {
	tests := []struct {
		name string
		cfg  SlidingWindowConfig
	}{
		{"zero limit", SlidingWindowConfig{Limit: 0, Window: time.Second}},
		{"negative limit", SlidingWindowConfig{Limit: -3, Window: time.Second}},
		{"zero window", SlidingWindowConfig{Limit: 3, Window: 0}},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			_, err := NewSlidingWindow("api", tt.cfg, nil, nil)
			var le *LimiterError
			if !errors.As(err, &le) || le.Code != ErrInvalidConfig {
				t.Fatalf("want ErrInvalidConfig, got %v", err)
			}
		})
	}
}

func TestSlidingWindowLimitsWithinWindow(t *testing.T) {
	clock := NewManualClock(time.Unix(0, 0))
	logger := &MemoryLogger{}
	cfg := SlidingWindowConfig{Limit: 2, Window: time.Minute}
	sw, err := NewSlidingWindow("api", cfg, clock, logger)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}

	if d := sw.Allow(); !d.Allowed || d.Remaining != 1 {
		t.Fatalf("call 1: got %+v, want allowed remaining=1", d)
	}
	if d := sw.Allow(); !d.Allowed || d.Remaining != 0 {
		t.Fatalf("call 2: got %+v, want allowed remaining=0", d)
	}
	denied := sw.Allow()
	if denied.Allowed {
		t.Fatalf("call 3: expected denial, got %+v", denied)
	}
	if denied.RetryAfter <= 0 || denied.RetryAfter > time.Minute {
		t.Errorf("RetryAfter = %s, want (0, 1m]", denied.RetryAfter)
	}
	if len(logger.Entries) != 3 {
		t.Errorf("expected 3 log entries, got %d", len(logger.Entries))
	}
}

func TestSlidingWindowEvictsExpired(t *testing.T) {
	clock := NewManualClock(time.Unix(0, 0))
	cfg := SlidingWindowConfig{Limit: 1, Window: time.Minute}
	sw, err := NewSlidingWindow("api", cfg, clock, nil)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}

	if d := sw.Allow(); !d.Allowed {
		t.Fatalf("first request should be allowed, got %+v", d)
	}
	if d := sw.Allow(); d.Allowed {
		t.Fatalf("second request within window should be denied, got %+v", d)
	}
	// After the window fully passes, the earlier hit is evicted and a new one fits.
	clock.Advance(time.Minute + time.Millisecond)
	if d := sw.Allow(); !d.Allowed {
		t.Errorf("request after window should be allowed, got %+v", d)
	}
}
