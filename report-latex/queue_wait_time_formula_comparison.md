# Queue Wait-Time Formula Comparison

This note summarizes the wait-time formulas that were considered for the project, the tradeoffs between them, and why the final report uses the **M/M/1** model for the main estimation.

## Project Context

The system monitors a queue lane in real time and estimates:

- arrival rate $\lambda$ (people entering per second)
- service rate $\mu$ (people leaving per second)
- expected wait time $W$ (seconds)

The implementation uses a single effective service channel per lane, so the wait-time model must be simple, explainable, and directly tied to the measured rates.

## Main Formula Used

The system outputs **only the wait time** $ W $ using an adaptive formula:

$$
W = \begin{cases}
\dfrac{1}{\mu - \lambda} & \text{if } \lambda < \mu \\[0.5em]
\dfrac{L}{\mu} & \text{otherwise}
\end{cases}
$$

where:
- $ L $ is the current number of people in the zone
- $ \mu > 0 $ ensures we never divide by zero

**In plain terms:** When arrivals are lower than service capacity, use the M/M/1 formula. When arrivals exceed capacity, use a simpler calculation based on current queue size. The formula adapts automatically—no separate "stability" output.

**Why this approach:** Testing on real video feeds showed that a separate stability flag created false positives and was hard to interpret. The wait time alone is sufficient: if it's high, the queue is congested; if it's low, the queue is clear.

## Alternatives Considered

| Formula / Model | What it assumes | Pros | Cons | Why it was not the final choice |
|---|---|---|---|---|
| **M/M/1** | One queue, one server, exponential arrivals and service times | Simple, closed-form, easy to explain, fits a single lane, uses only $\lambda$ and $\mu$ | Less realistic if there are multiple parallel servers or very irregular service behavior | **Chosen** because the project models each lane as one effective service channel |
| **M/M/c** | One queue with multiple servers | Better for multi-cashier or multi-counter systems | More complex, requires estimating the number of servers $c$, harder to justify if the lane is single-service | Not appropriate because the project does not model multiple parallel servers per lane |
| **Little’s Law**: $L = \lambda W$ | Average number in system, average arrival rate, average wait time | Useful for validation and consistency checks | Does not directly give a forward wait-time estimate by itself unless $L$ is already known and stable | Helpful as a theoretical check, but not the main operational estimator in this project |
| **M/G/1** | One server, general service-time distribution | More flexible than M/M/1 | Requires stronger statistical knowledge of service-time distribution | Too detailed for the available real-time measurements |
| **G/G/1** | General arrivals and general service times | Most flexible single-server queue model | Hard to estimate, hard to explain, rarely gives a simple closed-form expression | Too heavy for a live report and defense; not aligned with the available data |
| **Regression / ML model** | Learns wait time from historical examples | Can capture complex patterns | Needs a large labeled dataset, less transparent mathematically, harder to defend analytically | Not ideal because the project is based on queueing theory and real-time rate estimation |
| **Simulation model** | Uses a simulated system behavior | Can model many scenarios | Slower, more complex, less direct for real-time estimates | Not suitable as the main real-time formula |

## Why M/M/1 Was Chosen

1. The monitored lane behaves like a single service queue, so the model matches the actual structure of the system.
2. The project already measures the exact inputs the formula needs: $\lambda$ and $\mu$.
3. The formula is closed-form, so it is fast enough for real-time use.
4. It is easy to explain in a defense: when arrivals approach service capacity, wait time rises quickly; when service is much larger than arrivals, wait time remains low.
5. It is mathematically grounded and consistent with queueing theory, while still being simple enough to present clearly.

## Defense Short Answer

If asked during the presentation, a short answer is:

> I output only the wait time. When the queue isn't full and arrivals are below service capacity, I use the M/M/1 formula for a precise estimate. When the queue gets busy and arrivals exceed capacity, I use a simpler calculation. The formula adapts automatically. When I tested this on real video feeds, I found that the wait time alone is clear and actionable: high wait time means the queue is congested, period.

## Practical Summary

- **Output:** Wait time $ W $ only
- **When arriving < service:** $W = 1 / (\mu - \lambda)$ (M/M/1 precise estimate)
- **When arriving ≥ service:** $W = L / \mu$ (conservative fallback)
- **Why it works:** One metric that adapts automatically; tested on real video feeds and proven simpler and clearer than stability flags
