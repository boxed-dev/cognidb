# Hybrid generation: free-form default, intent mode opt-in

**Status:** accepted

v2 keeps **free-form generation** (LLM → SQL string → validate → execute) as the default path for compatibility and speed of delivery. We also ship **intent generation** as an explicit opt-in: LLM → query intent → deterministic SQL renderer → same policy and access checks. Documentation should steer high-assurance consumers toward intent mode over time.

**Considered:** free-form only; intent-first with free-form advanced-only; hybrid default free-form + intent opt-in.

**Why:** matches current codebase and SoTA guardrail stacks while leaving a path to higher assurance without blocking trust milestones (release, allowlists, adversarial tests). Intent mode is the durable differentiator; free-form remains the on-ramp.
