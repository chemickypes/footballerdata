# Project timeline

This page tells the story of `fanta-lab`: where it started, what it became through seven pillars of work, and where it's heading. It's not a technical changelog — the per-module READMEs cover that — but a narrative for anyone who wants to understand *why* the project is shaped the way it is.

## 1. Where we came from

`fanta-lab` started as a script built for a single moment of the season: the pre-season auction draft. The goal was simple and narrow — given a list of available players, produce a "fair" price to bid on each one, to be consulted on draft night and then set aside until the following year.

The statistical core of that first version was a quantile regression model (Gradient Boosting Regressor) trained on historical player data, able to estimate not a single number but three percentiles of expected end-of-season points: P10 (pessimistic scenario), P50 (median scenario), and P90 (optimistic scenario). From that distribution of expected points came VORP (Value Over Replacement Player), which compared each player to a hypothetical baseline replacement at the same position to arrive at a fair price consistent with the auction budget.

It was, in essence, a snapshot: a single calculation, run once, to decide how to spend a budget in a single evening. Everything that happened afterward — the seven pillars described below — is the story of how that snapshot became a film: a system that keeps observing, updating, and recalibrating its estimates across the entire 38-matchday season.

## 2. What we built (Pillars 1-7)

**Pillar 1 — Dual-track community/personal.** The first step of architectural maturity: separating a "community" configuration, meant to be shared and reproduced by anyone cloning the repository, from a "personal" configuration holding data and parameters specific to whoever runs the project for their own league. A cascading configuration layer driven by the `APP_ENV` environment variable made this split possible without duplicating code.

**Pillar 2 — Critical bugfixes.** A series of fixes that made the system reliable in production: a `player_id` fallback to guarantee training reproducibility even when the primary identifier is unavailable; improved resilience of Transfermarkt scraping, with fallback mechanisms for when pages change structure or stop responding; a recalibration of the Scala Slot percentiles to account for differences across positions; and a blueprint of dynamic percentages, rescaled against the league's actual budget instead of a fixed value.

**Pillar 3 — Dynamic midweek feed.** The most important statistical shift so far: the introduction of a data feed that refreshes automatically three times a week, across all 38 matchdays, via GitHub Actions and a dedicated orphan branch (`data-feed`) that hosts these updates without polluting the source code history. From this point on, estimates are no longer frozen at auction time — they stay alive for the entire season.

**Pillar 4 — Analytical modules.** The construction of tools designed for weekly use, not just pre-draft: a Weekly Lineup Solver based on mixed-integer linear programming (MILP) to choose the optimal lineup while respecting formation and position constraints; a Post-Draft Audit with Power Rankings to evaluate how one's own draft performed relative to opponents; and a Trade Machine capable of evaluating trades based on the marginal utility each player brings to a team, not just their raw value.

**Pillar 5 — Local AI copilot.** The introduction of a provider-agnostic AI assistant, able to run against different backends (including Ollama locally, at zero cost), to support the user in interpreting data and making tactical decisions without depending on a single vendor or recurring costs.

**Pillar 6 — Medical window and onboarding.** A growing focus on user experience: a fragility badge system (🟢🟡🔴) to flag injury risk for a player at a glance, and an interactive spotlight tutorial to guide new users through the app's features.

**Pillar 7 — This restructuring.** Reorganizing the repository into three areas — `core/`, `modules/`, `web/` — with explicit dependency boundaries, switching the license to PolyForm Noncommercial 1.0.0, and writing dedicated documentation for each module. This is the pillar that makes everything before it sustainable: without a clear structure, the accumulated functionality of Pillars 1-6 would have become progressively harder to maintain and extend.

The common thread across these seven pillars, statistically speaking, is the move from a point estimate calculated once to a system that continuously updates its own probabilities: bookmaker odds are "devigged" (stripped of their implicit margin) to extract clean probabilities, recent player form is weighted using an exponentially weighted moving average (EWMA) that gives more weight to recent matches, and the probability of starting is estimated and refreshed match after match. The result is a system that no longer photographs a single moment, but accompanies the user through the entire season.

## 3. Where we're going

The direction the project is moving in isn't a checklist of features, but an underlying idea: making statistical uncertainty more central, and more accessible, over time.

On one hand, we want the predictive engine to reason increasingly in terms of full distributions rather than single expected values — not "how many points will this player score", but "how likely is it that they score more or less than this threshold" — leaving it to the user, with their own context and risk appetite, to decide how to act on that information.

On the other hand, we want the AI copilot to gain progressively more autonomy in suggesting in-season decisions — not just answering questions, but actively proposing lineups, trades, or course corrections when the data signals a meaningful change.

Finally, and perhaps most importantly, we want all this statistical sophistication — quantiles, VORP, fragility indices — to remain, or become, accessible to people without a technical background. The value of a system like this doesn't lie in the complexity of its calculations, but in its ability to translate them into decisions that make sense to someone who plays fantasy football for fun, not to do data science.
