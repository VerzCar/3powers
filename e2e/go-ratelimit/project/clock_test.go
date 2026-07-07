package ratelimit

import (
	"testing"
	"time"
)

func TestManualClockAdvance(t *testing.T) {
	start := time.Date(2026, 1, 1, 0, 0, 0, 0, time.UTC)
	clock := NewManualClock(start)

	if got := clock.Now(); !got.Equal(start) {
		t.Fatalf("Now() = %v, want %v", got, start)
	}
	clock.Advance(90 * time.Second)
	if got := clock.Now(); !got.Equal(start.Add(90 * time.Second)) {
		t.Errorf("after Advance, Now() = %v, want %v", got, start.Add(90*time.Second))
	}
}

func TestSystemClockMovesForward(t *testing.T) {
	c := SystemClock{}
	first := c.Now()
	if c.Now().Before(first) {
		t.Errorf("system clock went backwards")
	}
}
