package ratelimit

// LogEntry is one structured log record emitted by a limiter.
type LogEntry struct {
	Level   string
	Message string
	Fields  map[string]any
}

// Logger is the small logging abstraction the limiters depend on. Tests supply
// a MemoryLogger; production supplies a transport-backed implementation without
// the strategies needing to change.
type Logger interface {
	Log(entry LogEntry)
}

// MemoryLogger collects entries in memory — the default in tests and in
// I/O-free code paths.
type MemoryLogger struct {
	Entries []LogEntry
}

// Log appends an entry.
func (m *MemoryLogger) Log(entry LogEntry) {
	m.Entries = append(m.Entries, entry)
}

// NopLogger discards every entry; the default when a limiter is built without a
// logger.
type NopLogger struct{}

// Log discards the entry.
func (NopLogger) Log(LogEntry) {}

// logDecision emits one structured record per Allow call.
func logDecision(logger Logger, name string, d Decision) {
	logger.Log(LogEntry{
		Level:   "info",
		Message: "rate limit decision",
		Fields: map[string]any{
			"limiter":   name,
			"allowed":   d.Allowed,
			"remaining": d.Remaining,
		},
	})
}
