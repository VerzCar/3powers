package ratelimit

import "time"

// Decision is the outcome of a single Allow call.
type Decision struct {
	// Allowed reports whether the request may proceed.
	Allowed bool
	// Remaining is the number of further requests permitted in the current
	// window immediately after this call (strategy-defined, best effort).
	Remaining int
	// RetryAfter is how long to wait before a request would next be allowed
	// when Allowed is false; it is zero when Allowed is true.
	RetryAfter time.Duration
}

// Limiter is the single interface both strategies implement. Allow consults the
// limiter's injected Clock, so callers never pass time in.
type Limiter interface {
	// Name identifies the limiter — its key in a Registry.
	Name() string
	// Allow records one request attempt and reports the decision.
	Allow() Decision
}
