# Model card — software v0.2, exploratory maturity

## Status and intended use

Exploratory, synthetic electricity investment model for inspecting methods, testing accounting and reproducing controlled experiments. Intended users are researchers and students comfortable with linear optimisation and investment economics. It is not calibrated, externally validated, peer-reviewed or suitable for policy, adequacy, financial or engineering decisions.

## Boundary

One electricity node; gas, peaker, wind and solar; fixed storage; continuous dispatch and planning investments. Default years 2026–2031. Each year uses one synthetic 168-hour chronological block repeated with weight 8760/168. This is not a statistically selected representative week. Investment choices are technology-specialist, price-taking, simultaneous and budget-limited. Assets retire at an exogenous age/date; no strategic bidding or endogenous mothballing.

The initial fleet deliberately creates scarcity. High unserved energy or prices in the example must not be interpreted as GB forecasts. All fixture costs, growth, VOLL, deratings and investor parameters are authored assumptions, not claimed current official values. Monetary amounts are constant illustrative GBP on one internally consistent price basis, with no estimated base-year price series.

## Outputs and interpretation

Capacity, investment decisions, prices, unserved energy, deterministic weighted scarcity hours, emissions, curtailment, settlement cashflows and discounted resource cost. Seed quantiles describe variation under the configured artificial expectation noise; they are not calibrated uncertainty intervals. Capacity payments are transfers, excluded from resource costs. A planner–ABM cost gap includes differences in foresight, finance and decision rules; it is not a causal estimate of market failure.

## Verification versus validation

The v0.2 GUI invokes the same synthetic model and displays saved assumptions. Its quick-run default uses 24 periods; users can select 48 or the CLI default of 168. UI usability and complete-year demand checks do not establish historical accuracy. See `WORKBENCH.md`.

Analytical dispatch/dual oracles, storage balance, objective reconstruction, vintage accounting, seeded replay and metamorphic checks establish selected internal properties. They do not establish external realism. NESO ingestion verification is separate from modelling: those observations are not substituted into the synthetic experiment. See the acceptance map and roadmap.

## Important omissions

No transmission, unit commitment, ramps, integer projects after allocation, forced outages, probabilistic LOLE, official Capacity Market auction, CfD, endogenous fuel/carbon prices, heat or hydrogen coupling, trained behavioural parameters, holdout validation, welfare decomposition or policy recommendation. Storage capacity is not optimised. There is no Mesa dependency: the small investor population is orchestrated directly in Python.

## Responsible communication

Use “exploratory investment experiment” and link a manifest when quoting results. Do not call a successful solver status “validated”, an 8,760-hour solver benchmark “calibrated annual evidence”, or a synthetic stress price an observed market price. Future scientific claims require separate acceptance evidence.
