package ratelimit

import (
	"math"
	"time"
)

// TokenBucketConfig parameterizes a token-bucket limiter: a bucket holding at
// most Capacity tokens that refills RefillTokens every RefillInterval. Each
// allowed request consumes one token.
type TokenBucketConfig struct {
	Capacity       int
	RefillTokens   int
	RefillInterval time.Duration
}

func (c TokenBucketConfig) validate() error {
	switch {
	case c.Capacity <= 0:
		return newError(ErrInvalidConfig, "capacity must be positive, got %d", c.Capacity)
	case c.RefillTokens <= 0:
		return newError(ErrInvalidConfig, "refill tokens must be positive, got %d", c.RefillTokens)
	case c.RefillInterval <= 0:
		return newError(ErrInvalidConfig, "refill interval must be positive, got %s", c.RefillInterval)
	}
	return nil
}

// TokenBucket is a Limiter implementing the token-bucket strategy. It starts
// full and refills continuously based on elapsed time.
type TokenBucket struct {
	name       string
	cfg        TokenBucketConfig
	clock      Clock
	logger     Logger
	tokens     float64
	lastRefill time.Time
}

// NewTokenBucket builds a token-bucket limiter, starting full. A nil clock uses
// SystemClock and a nil logger uses NopLogger.
func NewTokenBucket(name string, cfg TokenBucketConfig, clock Clock, logger Logger) (*TokenBucket, error) {
	if err := cfg.validate(); err != nil {
		return nil, err
	}
	if clock == nil {
		clock = SystemClock{}
	}
	if logger == nil {
		logger = NopLogger{}
	}
	return &TokenBucket{
		name:       name,
		cfg:        cfg,
		clock:      clock,
		logger:     logger,
		tokens:     float64(cfg.Capacity),
		lastRefill: clock.Now(),
	}, nil
}

// Name returns the limiter's name.
func (b *TokenBucket) Name() string { return b.name }

// Allow refills the bucket for the time elapsed since the last call, then
// consumes one token when available.
func (b *TokenBucket) Allow() Decision {
	b.refill(b.clock.Now())

	var decision Decision
	if b.tokens >= 1 {
		b.tokens--
		decision = Decision{Allowed: true, Remaining: int(b.tokens)}
	} else {
		decision = Decision{Allowed: false, RetryAfter: b.retryAfter()}
	}
	logDecision(b.logger, b.name, decision)
	return decision
}

func (b *TokenBucket) refill(now time.Time) {
	elapsed := now.Sub(b.lastRefill)
	if elapsed <= 0 {
		return
	}
	added := elapsed.Seconds() / b.cfg.RefillInterval.Seconds() * float64(b.cfg.RefillTokens)
	b.tokens = math.Min(float64(b.cfg.Capacity), b.tokens+added)
	b.lastRefill = now
}

// retryAfter estimates the wait until at least one token is available.
func (b *TokenBucket) retryAfter() time.Duration {
	needed := 1 - b.tokens
	perToken := b.cfg.RefillInterval.Seconds() / float64(b.cfg.RefillTokens)
	return time.Duration(needed * perToken * float64(time.Second))
}
