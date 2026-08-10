# Independent review of the revision-arm pre-registration

Written 2026-08-10 against `src/revision/README.md` §1–14 in the `revision-spec`
worktree, at commit `1d8af41`, before any coefficient existed. I did not write
that specification. Reviewing it rather than duplicating it is the only useful
thing a second session can do here.

The design is sound and in three places better than the one I was drafting. It
catches the two-auction problem, which I had missed: the project's 11-hour night
block straddles two operating days, so a single day-ahead gate cannot be defined
for it, and §8 redefines the outcome onto the hours that share one auction rather
than fudging the gate. §11's power gate is the only assumption-free one in the
project, and it says so in the right direction: it can fire "underpowered" and
cannot certify the converse.

Three things below should change before the run. The second is the one that
matters.

---

## 1. Anchor design verified, no change needed

I ran §7's three anchors over all 600 nights of the ten-season panel at a 10:30
ET gate. The failure I went looking for was anchor collapse: "the last issuance
at or before" a deadline silently returns the previous anchor's product when no
package lands in between, which sets `rev_pre` to exactly zero for a reason
unrelated to weather.

| check | result |
| --- | --- |
| A and B resolve to the same product | 0 of 600 nights |
| B and C resolve to the same product | 0 of 600 nights |
| issuances in the A→B window | median 4, minimum 1 |
| issuances in the B→C window | median 3, minimum 1 |
| any anchor missing the target 12Z period | 0 of 600 nights |

§7 reported the 32.5-hour anchor at 98.1% availability from a partial archive.
On the complete archive all three anchors carry the target period on every night.
The amendment from `g−24h` to `g−12h` holds up.

---

## 2. `rev_pre` and `rev_post` share anchor B, and the rounding error is the same
   size as the signal

    rev_pre  = S(B) − S(A)
    rev_post = S(C) − S(B)

Under an efficient forecast these are independent increments, which is what makes
§10's kill criterion 1 attractive. That independence breaks once S(B) is measured
with error, because the same error enters `rev_pre` with a plus sign and
`rev_post` with a minus sign. The induced covariance is −var(u), and it is there
whether or not the forecast is efficient.

§12 already records the source of that error: snow is published as inch ranges
and read as midpoints, so `01-03` becomes 2.0. What §12 treats as attenuation is
larger than that. On my descriptive pass the standard deviation of a successive
revision was **0.534 inches**, and the rounding grain on a `01-03` range is of
the same order. The measurement error is not small relative to the signal; it is
comparable to it.

The consequence lands squarely on the criterion the README calls "the sharpest
falsification available anywhere in this project." With two regressors carrying
correlated errors of opposite sign, ordinary least squares does not simply
attenuate both. A true `rev_pre` effect leaks into the estimated `rev_post`
coefficient. **A mechanical artifact can therefore fire kill criterion 1 and
declare the whole arm INVALID when nothing is wrong with the auction.**

Suggestions, cheapest first:

- **Regress `rev_post` on `rev_pre` directly.** One line, and it identifies which
  contamination is present rather than only whether one is. A negative slope
  means the shared rounding error dominates, which is the channel above. A
  positive slope means NWS revisions have momentum, which is a different problem
  with the opposite consequence. Run this before choosing a mitigation.
- Print `corr(rev_pre, rev_post)` next to criterion 1. If it is near zero the
  concern is idle and the criterion stands as written.
- Register the falsification in a second specification that regresses the spread
  on `rev_post` **without** `rev_pre`. That removes the shared-error channel, but
  it opens an omitted-variable one: if revisions have momentum, `rev_pre`'s true
  effect loads onto `rev_post` and criterion 1 fires spuriously from the other
  direction. Only worth doing if the diagnostic above comes back negative.
- The `snow_in_lo` sensitivity already in the pipeline changes the rounding rule
  rather than removing it. A revision built from the range *width* would separate
  the two, if it is worth the extra parameter.

---

## 3. Say what "SUPPORTS" supports

§10 outcome 2 reads "SUPPORTS if `rev_pre` is negative and significant at 5%,"
with no object. §1 motivates the whole arm from the α bound of §8.8b, which is a
statement about a **load forecaster** missing snowmaking.

A significant negative `rev_pre` says the day-ahead **price** moved with pre-gate
snow news. That is the market impounding the information, which is closer to the
opposite of a blind spot, and it involves a different agent from the one §1 is
about. The arm does escape the `cum_cold_h` collinearity that produced the α
bound, but it does not produce an α, and a reader coming from §1 will take
"SUPPORTS" to mean the blind-spot claim survived.

This project has twice paid for exactly this class of error: the sign of the
pre-registered prediction was read backwards and published, and Austria's mean
absolute forecast error was carried into a power table as a minimum detectable
effect. Both were labelling failures rather than arithmetic ones. Naming the
object of "SUPPORTS" costs one clause and closes it before the coefficient lands
rather than after.

---

## 4. Two smaller things

**Multiplicity is unregistered.** §10 carries two primaries (`rev_pre` and the
Vermont-minus-Rhode-Island differential) and the pipeline lists roughly eight
sensitivities: the 10:00 gate, all eight zones, the range lower bound, trace as
zero, Newey–West, the six-season join, the 11-hour block, and the night level.
Ten-odd looks at 5% give about a 40% chance that one comes back significant on
noise alone. Everything else in this repository is strict about this. Worth
registering that sensitivities are descriptive and cannot upgrade a null primary.

**The zone mean floats.** §6 keeps a night if at least three of four zones are
present, then takes an unweighted mean. The treatment is therefore sometimes a
3-zone mean and sometimes a 4-zone mean, which adds night-to-night variation that
is not weather. Worth reporting how many nights run on three zones; if it is a
handful, requiring all four is cleaner than averaging over a changing set.

---

## Caveat on my own numbers

The revision descriptives I quote came from a parse that predates `norm_zone()`
and therefore **excluded season 2016**, whose zone labels are upper case. Nine
seasons of ten. The shape holds; the exact figures should be restated from the
fixed parse before anyone quotes them.

**The 222 figure carries a second defect and should not be quoted at all.** My
exploratory script classified an issuance as post-gate with a fixed
`hour > 15.5 UTC` rule. That does no DST handling, which is the error §4.1 item 6
of the specification documents and attributes to an earlier draft of this file,
and it also marks a 02:26 UTC issuance as pre-gate when 02:26 UTC is 21:26 ET the
previous evening, long past the gate for the night it revises. The standard
deviation of 0.534 inches and the 42.9% of periods that never moved are not
affected by the gate rule. The 222 is wrong twice over. §7's anchors are the
correct construction and my §1 check above uses them.

The anchor verification in §1 ran against the 21:38 snapshot, before
`norm_zone()` landed. Anchor resolution depends only on issuance timestamps taken
from product filenames, which no parser edit changes, so those rows stand. The
one row that depends on the parse is "any anchor missing the target 12Z period,"
and it should be re-run on the fixed output to be exact.
