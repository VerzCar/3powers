package ratelimit

import "time"

// Clock supplies the current time to a limiter. Injecting it is what keeps the
// strategies deterministic: production wires SystemClock, tests wire a
// ManualClock they advance by hand.
type Clock interface {
	Now() time.Time
}

// SystemClock reads the wall clock.
type SystemClock struct{}

// Now returns the current wall-clock time.
func (SystemClock) Now() time.Time { return time.Now() }

// ManualClock is a Clock whose time only moves when Advance is called — the
// deterministic clock used throughout the tests.
type ManualClock struct {
	current time.Time
}

// NewManualClock returns a ManualClock fixed at start.
func NewManualClock(start time.Time) *ManualClock {
	return &ManualClock{current: start}
}

// Now returns the clock's current time.
func (c *ManualClock) Now() time.Time { return c.current }

// Advance moves the clock forward by d.
func (c *ManualClock) Advance(d time.Duration) { c.current = c.current.Add(d) }
