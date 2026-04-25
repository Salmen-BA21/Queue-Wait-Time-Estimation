# Queue Wait-Time Formula Comparison

This note summarizes the wait-time formulas that were considered for the project, the tradeoffs between them, and why the final report uses the **M/M/1** model for the main estimation.

## Project Context

The system monitors a queue lane in real time, estimates:

- arrival rate $\lambda$
- service rate $\mu$
- expected wait time $W$
- queue stability

The implementation uses a single effective service channel for each monitored lane, so the wait-time model must be simple, explainable, and directly tied to the measured rates.

## Main Formula Used

### M/M/1 wait-time model

$$
W = \frac{1}{\mu - \lambda}
$$

Valid when the queue is stable:

$$
\lambda < \mu
$$

### Fallback used in the project

When the queue is unstable but service is still observed, the implementation uses:

$$
W = \frac{L}{\mu}
$$

where $L$ is the number of people currently in the zone.

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

> I used the M/M/1 formula because the system models each monitored lane as one effective queue with one service channel. It gives a simple closed-form wait-time estimate from the measured arrival and service rates, so it is both mathematically justified and easy to use in real time. Other models, like M/M/c or G/G/1, were more complex and did not match the structure of the project as well.

## Practical Summary

- **Main estimator:** M/M/1
- **Stable case:** $W = 1 / (\mu - \lambda)$
- **Unstable fallback:** $W = L / \mu$
- **Why it fits:** simple, real-time, explainable, and aligned with a single-lane queue
