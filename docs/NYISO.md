# NYISO calibration record

The jurisdiction selected for calibration is New York, matching the existing N.Y.C.
price replay. The policy now includes its configured metered charge in both offer and
dispatch decisions. A participant-specific NYISO tariff case is still incomplete.

## Published rules and model inputs

Sources were read on 2026-10-20 and are registered in [Sources](SOURCES.md#nyiso-rules).
The 2018 filing is a historical proposal; it is not asserted to be the current tariff.
The 2020 FERC order records acceptance subject to further compliance. Neither replaces
the applicable tariff version and participant agreement for a commercial valuation.

| Item | Published evidence | Mapping and limit |
| --- | --- | --- |
| Minimum energy-market capability | NYISO's 2018 Order 841 filing, Part IV.A.1, pp. 12–13: at least 0.1 MW injection sustained for one hour. | `qmin = 0.1` alone is insufficient. At least 0.1 MWh must reach the grid; the stored-energy requirement also depends on discharge efficiency. |
| Generic duration screen | `qual` compares usable stored energy divided by rated power with `qdur`. | This tests duration at rated output, not duration at NYISO's minimum output. Setting `qdur = 1` would reject some resources allowed by the published minimum. No NYISO-labelled configuration is supplied. |
| Assumed study battery | 1 MW charge/discharge, 4 MWh usable stored energy, discharge efficiency 0.92. | The full battery can deliver 3.68 MWh, exceeding the historical minimum capability. These are study assumptions, not participant registration or certification data. |
| Charging energy | FERC's 2020 order, paragraph 4, describes wholesale LMP pricing for energy stored for wholesale resale. | The replay already pays the real-time energy price for charging. Adding that energy price again as `tar` would double count it. |
| Transmission charging | The 2020 order, paragraphs 6 and 8–10, addresses transmission charges and the dispatch conditions for charging withdrawals. | A symmetric flat charge on both metered directions cannot reproduce conditional transmission charging. |
| Settlement components | NYISO's ESR Settlements Quick Reference Sheet lists TSC/NTAC and Rate Schedule 1, alongside energy and other services. | A zero `tar` is the unchanged study default, not evidence of a tariff exemption. A positive stress-test `tar` is assumed, not a NYISO rate. |

## What prevents a complete tariff case

The case needs the actual point of interconnection and transmission district, the
participant's registration and applicable agreements, the relevant tariff effective
dates and rates, and the dispatch status that determines transmission-charge treatment.
The current Accounting and Billing Manual URL returned a JavaScript verification page
during this review. Its contents were not inferred from that failed retrieval.

No numerical NYISO rate is fitted here. The remaining implementation must distinguish
charge bases and directions before representing them in an objective and settlement.
The generic rate mechanism can already test an assumed rate without choosing trades
that ignore it. Full acceptance, price taking, self-dispatch and zonal rather than
resource-node prices remain study assumptions. No annual replay was run for calibration.
