package ratelimit

import "time"

// SlidingWindowConfig parameterizes a sliding-window limiter: at most Limit
// requests may be allowed within any trailing Window.
type SlidingWindowConfig struct {
	Limit  int
	Window time.Duration
}

func (c SlidingWindowConfig) validate() error {
	switch {
	case c.Limit <= 0:
		return newError(ErrInvalidConfig, "limit must be positive, got %d", c.Limit)
	case c.Window <= 0:
		return newError(ErrInvalidConfig, "window must be positive, got %s", c.Window)
	}
	return nil
}

// SlidingWindow is a Limiter implementing the sliding-window-log strategy: it
// keeps the timestamps of allowed requests inside the trailing window and
// admits a new one only while fewer than Limit remain.
type SlidingWindow struct {
	name   string
	cfg    SlidingWindowConfig
	clock  Clock
	logger Logger
	hits   []time.Time
}

// NewSlidingWindow builds a sliding-window limiter. A nil clock uses
// SystemClock and a nil logger uses NopLogger.
func NewSlidingWindow(name string, cfg SlidingWindowConfig, clock Clock, logger Logger) (*SlidingWindow, error) {
	if err := cfg.validate(); err != nil {
		return nil, err
	}
	if clock == nil {
		clock = SystemClock{}
	}
	if logger == nil {
		logger = NopLogger{}
	}
	return &SlidingWindow{name: name, cfg: cfg, clock: clock, logger: logger}, nil
}

// Name returns the limiter's name.
func (w *SlidingWindow) Name() string { return w.name }

// Allow evicts requests that have aged out of the window, then admits the new
// request when capacity remains.
func (w *SlidingWindow) Allow() Decision {
	now := w.clock.Now()
	w.evict(now)

	var decision Decision
	if len(w.hits) < w.cfg.Limit {
		w.hits = append(w.hits, now)
		decision = Decision{Allowed: true, Remaining: w.cfg.Limit - len(w.hits)}
	} else {
		oldest := w.hits[0]
		decision = Decision{Allowed: false, RetryAfter: w.cfg.Window - now.Sub(oldest)}
	}
	logDecision(w.logger, w.name, decision)
	return decision
}

// evict drops timestamps that fall outside the trailing window ending at now.
func (w *SlidingWindow) evict(now time.Time) {
	cutoff := now.Add(-w.cfg.Window)
	i := 0
	for i < len(w.hits) && !w.hits[i].After(cutoff) {
		i++
	}
	w.hits = w.hits[i:]
}
