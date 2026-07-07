package ratelimit_test

import (
	"testing"
	"time"

	ratelimit "github.com/threepowers/go-ratelimit"
)

// TestRegistryDrivesBothStrategies exercises the public API end to end: two
// different strategies registered under one registry, each enforcing its own
// policy against a shared deterministic clock.
func TestRegistryDrivesBothStrategies(t *testing.T) {
	clock := ratelimit.NewManualClock(time.Unix(0, 0))
	reg := ratelimit.NewRegistry()

	bucket, err := ratelimit.NewTokenBucket("burst", ratelimit.TokenBucketConfig{
		Capacity: 2, RefillTokens: 1, RefillInterval: time.Second,
	}, clock, &ratelimit.MemoryLogger{})
	if err != nil {
		t.Fatalf("NewTokenBucket: %v", err)
	}
	window, err := ratelimit.NewSlidingWindow("steady", ratelimit.SlidingWindowConfig{
		Limit: 1, Window: time.Minute,
	}, clock, &ratelimit.MemoryLogger{})
	if err != nil {
		t.Fatalf("NewSlidingWindow: %v", err)
	}

	for _, l := range []ratelimit.Limiter{bucket, window} {
		if err := reg.Register(l); err != nil {
			t.Fatalf("Register %q: %v", l.Name(), err)
		}
	}

	cases := []struct {
		limiter string
		want    []bool // expected Allowed for three successive calls
	}{
		{"burst", []bool{true, true, false}},   // capacity 2, then empty
		{"steady", []bool{true, false, false}}, // limit 1 per window
	}
	for _, tc := range cases {
		t.Run(tc.limiter, func(t *testing.T) {
			l, err := reg.Get(tc.limiter)
			if err != nil {
				t.Fatalf("Get %q: %v", tc.limiter, err)
			}
			for i, want := range tc.want {
				if got := l.Allow().Allowed; got != want {
					t.Errorf("%s call %d: allowed=%v, want %v", tc.limiter, i+1, got, want)
				}
			}
		})
	}
}
