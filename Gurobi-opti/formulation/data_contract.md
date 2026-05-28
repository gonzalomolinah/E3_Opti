# Data Contract

This document defines the JSON data required by `formulation/model.tex`.
All generated datasets must set `metadata.synthetic` to `true` and must not
claim to represent a real hospital unless real sources are explicitly provided.

## Sets

| Name | Type | Validation |
|---|---|---|
| `H` | hospitals | Nonempty list of unique strings. |
| `G` | blood types | Nonempty list of unique strings. |
| `T` | periods | Exactly `[1, ..., Tmax]`. |
| `L` | maximum useful life | Positive integer. |
| `U` | useful-life levels | Exactly `[1, ..., L]`. |
| `N` | nodes | Exactly `["0"] + H`; node `"0"` is the central bank. |
| `C` | compatible donor-receiver pairs | Subset of `G x G`; must match `compatibility` entries with value `1`. |

## Parameters

| Name | LaTeX | Indices | Unit | Validation |
|---|---|---|---|---|
| `demand` | `d_{h,g,t}` | `H x G x T` | blood units | Complete, numeric, nonnegative. |
| `donations` | `b_{g,t}` | `G x T` | blood units | Complete, numeric, nonnegative. |
| `initial_inventory` | `I^0_{n,g}` | `N x G` | blood units | Complete, numeric, nonnegative; assumed useful life `L`. |
| `storage_capacity` | `K_n` | `N` | blood units | Complete, numeric, nonnegative. |
| `travel_time` | `tau_h` | `H` | periods | Complete, integer, nonnegative. |
| `shortage_penalty` | `p` | scalar | cost/unit | Numeric, nonnegative. |
| `expiration_penalty` | `eta` | scalar | cost/unit | Numeric, nonnegative. |
| `compatibility` | `c_{g,g'}` | `G x G` | binary | Complete, value in `{0, 1}`. |
| `use_penalty` | `alpha_g` | `G` | cost/unit | Complete, numeric, nonnegative. |
| `substitution_penalty` | `beta_{g,g'}` | `G x G` | cost/unit | Optional in raw JSON/CSV; complete after loading. Defaults to `0` when `g = g'` and `5` when `g != g'`. |
| `big_m` | `M` | scalar | blood units | Positive and at least the maximum total hospital-period demand. |
| `max_transport` | `Q_t` | `T` | blood units/period | Complete, numeric, nonnegative. |

## Plausibility Notes

The checks in `src/validate_data.py` separate hard formulation requirements from
soft plausibility warnings. Synthetic toy instances may be intentionally scaled
down, but comments and reports should still explain that the values are scaled.

The model uses a simplified travel-time treatment. `travel_time` does not delay
arrivals across periods; it is used as an objective penalty and as a feasibility
filter for shipments whose remaining useful life is not long enough. Inventory
capacity is measured at the end of each period.

All quantities represent counts of blood bags and are modeled as nonnegative
integer decision variables. Input quantities should therefore be integer-valued.

The substitution penalty `beta[g,g']` encourages exact blood-type matches when
possible and reserves flexible/scarce donor types for cases where substitution is
really useful. It does not make compatible transfusions invalid; it only makes
them slightly more expensive than exact matches.

- RBC demand scales with hospital size. CDC reports about 29,000 RBC units
  needed per day in the United States, and AABB's 2023 NBCUS summary reports
  10.32M RBC units transfused in 2023. Sources:
  <https://www.cdc.gov/blood-safety/about/index.html> and
  <https://www.aabb.org/news-resources/news/article/2025/03/17/results-of-2023-nbcus-suggest-continued-stabilization-of-the-blood-supply>.
- Standard RBC shelf life is commonly 42 days. Source:
  <https://professionaleducation.blood.ca/en/transfusion/clinical-guide/blood-components>.
- RBC compatibility should follow ABO/Rh red-cell transfusion rules. O-negative
  is the universal red-cell donor. Source:
  <https://prod-www.redcrossblood.org/donate-blood/blood-types.html>.
- Hospital RBC inventory around 4-6 days of average daily use is a common
  management reference. Source:
  <https://profedu.blood.ca/en/transfusion/best-practices/blood-utilization-best-practices/blood-system-inventory-management-best>.
- Typical hospital-issued blood-product wastage is often reported in the 0-6%
  range, with higher values in some settings. Sources:
  <https://pubmed.ncbi.nlm.nih.gov/23808486/>,
  <https://aplm.kglmeridian.com/view/journals/arpa/126/2/article-p150.xml>,
  and <https://pubmed.ncbi.nlm.nih.gov/25035674/>.

## Warnings

Validation should warn when:

- `travel_time[h] >= L`, because all shipments to hospital `h` are blocked by
  the transfer feasibility constraint.
- A node's initial inventory exceeds its storage capacity.
- A hospital's capacity is above 10 days of its average daily demand, because
  excessive inventory can raise expiration risk.
- A computed solution reports wastage above 6%; wastage above 10% should be
  interpreted as a stress or poor-inventory scenario unless documented.
