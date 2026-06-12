# Quarterly Fundamentals Review: Apple Inc. (AAPL)

**To:** Investment file
**From:** [Your name]
**Date:** [Date]
**Re:** Q[X] FY20[XX] results — revenue trajectory, margin quality, and 4-quarter outlook
**Prepared with:** FinScope (SEC EDGAR 10-Q/10-K data; methodology in §6)

---

## 1. Executive summary

Apple reported revenue of **$[XX.X]B** in its latest filed quarter (period
ended [date]), [up/down] **[X.X]%** year over year. Net margin stood at
**[XX.X]%**, [expanding/compressing/holding steady] versus [XX.X]% four
quarters ago. A level forecast backtested at **[X.X]% MAPE** over the last
four quarters projects revenue of roughly **$[XX]B–$[XX]B** per quarter over
the next year, before seasonality.

> DECISION POINT — your one-sentence verdict goes here. Pick the honest one:
> "Fundamentals remain steady with no deterioration visible in the filings,"
> or "Growth is decelerating while margins hold, which bears watching," or
> whatever the numbers actually say. This sentence is the memo. Everything
> below is evidence for it.

[Your verdict sentence.]

---

## 2. Revenue trajectory

The last eight filed quarters (figures from 10-Q/10-K filings via EDGAR;
Q4 derived as FY minus reported quarters):

| Quarter end | Revenue | QoQ | YoY |
|---|---|---|---|
| [date] | $[XX.XX]B | [+/−X.X]% | [+/−X.X]% |
| [date] | $[XX.XX]B | [+/−X.X]% | [+/−X.X]% |
| ... | ... | ... | ... |

*(Paste the eight rows from the memo data pack, Section 2.)*

**Reading the pattern.** Apple's quarters are strongly seasonal — the
December quarter (holiday + new iPhone cycle) consistently towers over the
rest — so **YoY is the meaningful growth measure**, not QoQ. The recent YoY
prints of [list the last 3–4 YoY figures] indicate
[accelerating / steady / decelerating] top-line growth.

> DECISION POINT — say which it is and how confident the data lets you be.
> Two or three quarters is a hint, not a trend; say so if so.

[Your 2–3 sentence interpretation.]

---

## 3. Margin quality

| Quarter end | Gross margin | Operating margin | Net margin |
|---|---|---|---|
| [date] | [XX.X]% | [XX.X]% | [XX.X]% |
| ... | ... | ... | ... |

*(Paste from the data pack, Section 3.)*

Margins answer the question revenue can't: is the business getting **better**
or just bigger? Over these eight quarters, gross margin has
[expanded/compressed/held] from [XX.X]% to [XX.X]%, and net margin from
[XX.X]% to [XX.X]%.

> DECISION POINT — interpret. Expanding margins on flat revenue is mix-shift
> or pricing power (for Apple, typically the growing services share);
> compressing margins on growing revenue suggests the growth is being bought.
> Note the December quarter's margins also run seasonally rich.

[Your 2–3 sentence interpretation.]

---

## 4. Outlook: a disciplined four-quarter forecast

FinScope's production model (exponential smoothing on the level) projects
quarterly revenue of approximately:

| Quarter | Forecast |
|---|---|
| [20XXQX] | $[XX.X]B |
| [20XXQX] | $[XX.X]B |
| [20XXQX] | $[XX.X]B |
| [20XXQX] | $[XX.X]B |

Backtested on the last four reported quarters, the model's MAPE is
**[X.X]%**.

**Stated limitation — and why it's kept.** The model deliberately projects
the level, not Apple's pronounced December seasonality, so it will
under-forecast December quarters and over-forecast the others; the MAPE
above prices in exactly that cost. In FinScope's champion/challenger
backtesting on comparable data, seasonal index models *underperformed* the
simple level when history is short — twelve estimated indices overfit noise
faster than they capture signal. A forecast with an honest, measured error
beats a sophisticated one with an unmeasured error.

> DECISION POINT — if the seasonal model in YOUR backtest for AAPL actually
> wins (Apple has long, strongly seasonal history — it might), say that
> instead and use it. Report whichever the evidence supports. That is the
> entire point of the framework.

---

## 5. Risks and watch items

> Keep this to 3–4 bullets, each one tied to something observable in the next
> filing — that's what separates a watch list from hand-waving. Examples:

- **YoY deceleration**: if the next quarter's YoY growth falls below [X]%, the
  [steady-growth] thesis in §2 weakens.
- **Margin reversal**: net margin below [XX]% in a non-December quarter would
  break the §3 pattern.
- **Concentration / cycle risk**: revenue remains tied to the iPhone cycle;
  the model knows nothing about product launches and will miss step-changes.
- **Model risk**: a [X.X]% MAPE on history does not bound the error on a
  structurally different future.

---

## 6. Methodology and data note

All figures are from Apple's 10-Q and 10-K filings retrieved through the
SEC's EDGAR company-facts API and parsed by FinScope
([github.com/anichan2004/finscope](https://github.com/anichan2004/finscope)).
Concept mapping handles inconsistent XBRL tagging across filers; **Q4 figures
are derived as fiscal year minus the three reported quarters**, since US
filers do not file a standalone Q4 income statement. The revenue forecast is
simple exponential smoothing selected by holdout backtest under a
champion/challenger framework; MAPE is reported on the last four quarters
held out of training. This memo is an analytical exercise, not investment
advice.
