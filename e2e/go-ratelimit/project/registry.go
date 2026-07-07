package ratelimit

import (
	"sort"
	"sync"
)

// Registry tracks named limiters so a service can look one up per key — per
// route, per tenant, per API client. It is safe for concurrent use.
type Registry struct {
	mu       sync.Mutex
	limiters map[string]Limiter
}

// NewRegistry returns an empty registry.
func NewRegistry() *Registry {
	return &Registry{limiters: make(map[string]Limiter)}
}

// Register adds a limiter under its name, returning a typed error when the name
// is already registered.
func (r *Registry) Register(limiter Limiter) error {
	r.mu.Lock()
	defer r.mu.Unlock()
	name := limiter.Name()
	if _, ok := r.limiters[name]; ok {
		return newError(ErrDuplicateLimiter, "limiter %q already registered", name)
	}
	r.limiters[name] = limiter
	return nil
}

// Get returns the limiter registered under name, or a typed error when absent.
func (r *Registry) Get(name string) (Limiter, error) {
	r.mu.Lock()
	defer r.mu.Unlock()
	limiter, ok := r.limiters[name]
	if !ok {
		return nil, newError(ErrUnknownLimiter, "no limiter registered as %q", name)
	}
	return limiter, nil
}

// Names returns the registered limiter names, sorted for a stable order.
func (r *Registry) Names() []string {
	r.mu.Lock()
	defer r.mu.Unlock()
	names := make([]string, 0, len(r.limiters))
	for name := range r.limiters {
		names = append(names, name)
	}
	sort.Strings(names)
	return names
}

// Len reports how many limiters are registered.
func (r *Registry) Len() int {
	r.mu.Lock()
	defer r.mu.Unlock()
	return len(r.limiters)
}
