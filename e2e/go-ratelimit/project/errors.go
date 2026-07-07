// Package ratelimit provides small, in-memory request rate limiters behind a
// single Limiter interface: a token-bucket strategy and a sliding-window
// strategy, plus a registry that tracks named limiters.
//
// The package is deliberately I/O-free and deterministic. Time is supplied
// through an injectable Clock rather than read from the wall clock inside the
// strategies, so behaviour is fully reproducible under test — no network, no
// database, no sleeping.
package ratelimit

import "fmt"

// ErrorCode is a stable, typed classification for a LimiterError so callers
// branch on the code instead of parsing messages.
type ErrorCode string

const (
	// ErrInvalidConfig marks a limiter constructed with invalid parameters.
	ErrInvalidConfig ErrorCode = "INVALID_CONFIG"
	// ErrUnknownLimiter marks a lookup for a name the registry does not hold.
	ErrUnknownLimiter ErrorCode = "UNKNOWN_LIMITER"
	// ErrDuplicateLimiter marks registering a name that is already taken.
	ErrDuplicateLimiter ErrorCode = "DUPLICATE_LIMITER"
)

// LimiterError is the single error type every failure path in the package
// returns. Its Code is the stable discriminator.
type LimiterError struct {
	Code    ErrorCode
	Message string
}

// Error renders the code and message.
func (e *LimiterError) Error() string {
	return fmt.Sprintf("%s: %s", e.Code, e.Message)
}

func newError(code ErrorCode, format string, args ...any) *LimiterError {
	return &LimiterError{Code: code, Message: fmt.Sprintf(format, args...)}
}
