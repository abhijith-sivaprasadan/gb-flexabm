# MX02 — investor-entry frontier: why a payment can be impotent

The `Investor.request` rule is **not smooth investment supply**. It makes
a positive/negative profitability decision and, only after entry, submits
a fixed project-block count limited by *exogenous annual budget and the
technology construction ceiling*. Once profitable, a larger capacity
payment alone cannot increase the request until other model states change.

For fixed expected energy margin `m` (GBP/MW-year), project installed
capital cost `C` (GBP/MW), hurdle rate `h`, construction lead time `L`,
lifetime `T`, fixed cost `F`, risk haircut
`R = risk_aversion × forecast_noise_fraction × |m|`,
threshold `H` (GBP/MW), derating `d`, and capacity payment `p`
(GBP/kW-year):

```
A = sum((1+h)^(-t), t = L...L+T-1)
NPV(p) = -C + A * (m - F - R + 1000*d*p)
positive investment request iff NPV(p) > H
p* = max(0, [ (C+H)/A - m + F + R ] / (1000*d))
```

This is a **conditional exact algebraic frontier**, not an estimated
investment willingness-to-pay. At exactly `p*` request stays zero
because the implementation checks `score <= threshold`.

The module fails closed and reports no price-only entry frontier if:
no derated payment (`d=0`), zero CAPEX under this version's request
contract, annual budget cannot finance **one full project block**, or
commissioning would fall after the final model year. If NPV is already
above threshold at zero payment, the investor is fully active, and
increasing p does not expand the request under fixed inputs.

Caveat: expected margin `m` is **endogenous to the price/dispatch path**.
The formula does not predict an entire multi-year dynamic equilibrium:
it is valid for the investor's local annual decision **conditional on the
same observed expected margin**. Dynamic counterfactuals must re-solve
the physical dispatch/planner system as MX01 does. Not a GB market
empirical estimate.

Tests check the strict just-above/just-below threshold against
`Investor.request` and explicit budget/horizon/zero-derating negative controls.
