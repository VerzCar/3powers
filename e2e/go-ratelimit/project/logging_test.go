package ratelimit

import "testing"

func TestMemoryLoggerRecords(t *testing.T) {
	logger := &MemoryLogger{}
	logDecision(logger, "api", Decision{Allowed: true, Remaining: 3})

	if len(logger.Entries) != 1 {
		t.Fatalf("expected 1 entry, got %d", len(logger.Entries))
	}
	entry := logger.Entries[0]
	if entry.Level != "info" {
		t.Errorf("level = %q, want info", entry.Level)
	}
	if entry.Fields["limiter"] != "api" {
		t.Errorf("limiter field = %v, want api", entry.Fields["limiter"])
	}
	if entry.Fields["allowed"] != true {
		t.Errorf("allowed field = %v, want true", entry.Fields["allowed"])
	}
	if entry.Fields["remaining"] != 3 {
		t.Errorf("remaining field = %v, want 3", entry.Fields["remaining"])
	}
}

func TestNopLoggerDiscards(t *testing.T) {
	// The nop logger must accept a log call without panicking and keep no state.
	logger := NopLogger{}
	logDecision(logger, "api", Decision{Allowed: false})
}
