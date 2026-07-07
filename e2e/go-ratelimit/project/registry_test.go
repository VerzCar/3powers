package ratelimit

import (
	"errors"
	"testing"
	"time"
)

func newTestBucket(t *testing.T, name string) *TokenBucket {
	t.Helper()
	tb, err := NewTokenBucket(name, TokenBucketConfig{
		Capacity: 1, RefillTokens: 1, RefillInterval: time.Second,
	}, NewManualClock(time.Unix(0, 0)), nil)
	if err != nil {
		t.Fatalf("building test bucket: %v", err)
	}
	return tb
}

func TestRegistryRegisterAndGet(t *testing.T) {
	reg := NewRegistry()
	tb := newTestBucket(t, "api")
	if err := reg.Register(tb); err != nil {
		t.Fatalf("Register: %v", err)
	}
	if reg.Len() != 1 {
		t.Errorf("Len() = %d, want 1", reg.Len())
	}

	got, err := reg.Get("api")
	if err != nil {
		t.Fatalf("Get: %v", err)
	}
	if got.Name() != "api" {
		t.Errorf("Get returned %q, want api", got.Name())
	}
}

func TestRegistryDuplicate(t *testing.T) {
	reg := NewRegistry()
	if err := reg.Register(newTestBucket(t, "api")); err != nil {
		t.Fatalf("first Register: %v", err)
	}
	err := reg.Register(newTestBucket(t, "api"))
	var le *LimiterError
	if !errors.As(err, &le) || le.Code != ErrDuplicateLimiter {
		t.Fatalf("want ErrDuplicateLimiter, got %v", err)
	}
}

func TestRegistryUnknown(t *testing.T) {
	reg := NewRegistry()
	_, err := reg.Get("missing")
	var le *LimiterError
	if !errors.As(err, &le) || le.Code != ErrUnknownLimiter {
		t.Fatalf("want ErrUnknownLimiter, got %v", err)
	}
}

func TestRegistryNamesSorted(t *testing.T) {
	reg := NewRegistry()
	for _, name := range []string{"gamma", "alpha", "beta"} {
		if err := reg.Register(newTestBucket(t, name)); err != nil {
			t.Fatalf("Register %q: %v", name, err)
		}
	}
	got := reg.Names()
	want := []string{"alpha", "beta", "gamma"}
	if len(got) != len(want) {
		t.Fatalf("Names() = %v, want %v", got, want)
	}
	for i := range want {
		if got[i] != want[i] {
			t.Errorf("Names()[%d] = %q, want %q", i, got[i], want[i])
		}
	}
}
