# Deferred general optimization sequence

Moved from Decisions at baseline `8e4637e`. These unimplemented topics are outside
the current electricity and storage work; this is not an active implementation plan.

Deferred items from the former remaining-work list: variable pit-wall angles by direction
and rock type; quadratic generation offers; mine production scheduling with periods,
discounting and capacity limits. The market-related work remains in active Decisions.

## Model sequence

| Stage | Model | Class |
| --- | --- | --- |
| Built | Ultimate pit limit | Maximum closure |
| Built | Unit commitment and pricing | Mixed-integer model with dual prices |
| Built | pglib-uc reference commitment | Mixed-integer model, benchmarked, not priced |
| Exact flow | Shortest path, maximum flow, transportation, transshipment, assignment | Network flow |
| Branch point | Integer minimum-cost flow with one budget row | Integer optimization may be NP-hard |
| Integer network | Production scheduling, multicommodity flow, fixed-charge flow | Mixed-integer optimization |
| Integer selection | Facility location and set covering | Mixed-integer optimization |
| Bilevel network | Network interdiction | Bilevel optimization, often reformulated by duality |
