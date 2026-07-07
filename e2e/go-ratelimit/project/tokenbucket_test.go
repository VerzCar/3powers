package ratelimit

import (
	"errors"
	"testing"
	"time"
)

func TestNewTokenBucketInvalidConfig(t *testing.T) {
	tests := []struct {
		name string
		cfg  TokenBucketConfig
	}{
		{"zero capacity", TokenBucketConfig{Capacity: 0, RefillTokens: 1, RefillInterval: time.Second}},
		{"negative refill", TokenBucketConfig{Capacity: 1, RefillTokens: -1, RefillInterval: time.Second}},
		{"zero interval", TokenBucketConfig{Capacity: 1, RefillTokens: 1, RefillInterval: 0}},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			_, err := NewTokenBucket("api", tt.cfg, nil, nil)
			var le *LimiterError
			if !errors.As(err, &le) || le.Code != ErrInvalidConfig {
				t.Fatalf("want ErrInvalidConfig, got %v", err)
			}
		})
	}
}

func TestTokenBucketDrainsThenRefills(t *testing.T) {
	clock := NewManualClock(time.Unix(0, 0))
	logger := &MemoryLogger{}
	cfg := TokenBucketConfig{Capacity: 2, RefillTokens: 1, RefillInterval: time.Second}
	tb, err := NewTokenBucket("api", cfg, clock, logger)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}

	// Two tokens available, so the first two calls pass and the third is denied.
	if d := tb.Allow(); !d.Allowed || d.Remaining != 1 {
		t.Fatalf("call 1: got %+v, want allowed remaining=1", d)
	}
	if d := tb.Allow(); !d.Allowed || d.Remaining != 0 {
		t.Fatalf("call 2: got %+v, want allowed remaining=0", d)
	}
	denied := tb.Allow()
	if denied.Allowed {
		t.Fatalf("call 3: expected denial, got %+v", denied)
	}
	if denied.RetryAfter <= 0 || denied.RetryAfter > time.Second {
		t.Errorf("call 3 RetryAfter = %s, want (0, 1s]", denied.RetryAfter)
	}

	// One interval later a single token has refilled.
	clock.Advance(time.Second)
	if d := tb.Allow(); !d.Allowed {
		t.Errorf("after refill: expected allow, got %+v", d)
	}

	if len(logger.Entries) != 4 {
		t.Errorf("expected 4 log entries, got %d", len(logger.Entries))
	}
}

func TestTokenBucketRefillCapsAtCapacity(t *testing.T) {
	clock := NewManualClock(time.Unix(0, 0))
	cfg := TokenBucketConfig{Capacity: 3, RefillTokens: 1, RefillInterval: time.Second}
	tb, err := NewTokenBucket("api", cfg, clock, nil)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	// Drain one, then let a very long time pass; the bucket must not exceed cap.
	tb.Allow()
	clock.Advance(time.Hour)
	allowed := 0
	for i := 0; i < 10; i++ {
		if tb.Allow().Allowed {
			allowed++
		}
	}
	if allowed != cfg.Capacity {
		t.Errorf("allowed %d after long idle, want %d (capped)", allowed, cfg.Capacity)
	}
}
