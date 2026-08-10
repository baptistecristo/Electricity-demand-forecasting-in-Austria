# The futures leg: is there a market to trade the load in?

> **STATUS: liquidity gate only. No coefficient is estimated here, and none can
> be.** This directory answers the question that has to be settled before a
> futures price test can be designed at all, and the answer closes the design
> off. That is the result.

## 1. What this is, and how it sits against the spot test

`src/price/README.md` §1 argues that a monthly baseload futures contract cannot
carry a snowmaking signal, because eighteen hours of wet-bulb news is averaged
away inside a calendar month. That argument stands and nothing here overturns it.

But it is an argument about the *day-to-day* variation the Austrian design runs
on, and it does not dispose of futures entirely. A calendar-month off-peak
contract settles on the average of that month's off-peak day-ahead LMPs, so a
snowmaking premium that is present in most cold nights of a November would sit in
the November settlement as a level. The seasonal question — *do the winter
off-peak months carry a premium the summer ones do not, in the zones with the
guns* — is a question a futures curve could in principle answer where the spot
test cannot, because it is asked at the horizon at which snowmaking is planned
rather than dispatched.

The futures leg asks a different question at a different horizon from the spot
leg. This directory establishes that New Hampshire cannot be asked it, and why.

**New Hampshire rather than Vermont** because Vermont has no listed futures
contract to test. The CFTC filing `rule021015nodaldcm002`, which tabulates every
ISO-NE contract on ICE against its Nodal equivalent, covers the Internal Hub and
six zones — Connecticut, Maine, NEMA/Boston, New Hampshire, SE Mass and WC Mass.
**Vermont and Rhode Island are not on it.** The zone where the load test in
`src/vermont/README.md` found its coefficient is the one zone in ISO-NE that no
exchange has ever bothered to list. New Hampshire is the neighbouring zone that
is listed, and the closest thing to a tradable expression of the finding. It
is also the third-ranked snowmaking state in the desk-scoping table of the root
`README.md` §8.8 (22–54 GWh/season against ~1.25 GW of winter overnight load),
and `src/vermont/README.md` §6.3 puts its load coefficient at −0.0118 (0.0074),
the third most negative of eight zones. If any zone outside Vermont should carry
a tradable snowmaking premium, it is this one.

## 2. The instrument

The same instrument is listed on three exchanges. All three settle on the
day-ahead LMP at ISO-NE's New Hampshire load zone, node `.Z.NEMHAMPSHIRE` (4002),
averaged over the off-peak block of a calendar month.

| venue | code | size | product |
| --- | --- | --- | --- |
| CME / NYMEX | **AU3** | 5 MW | ISO New England New Hampshire Zone 5 MW Off-Peak Calendar-Month Day-Ahead LMP Futures |
| ICE Futures U.S. | **IHD** | 1 MW | ISO New England New Hampshire Day-Ahead Off-Peak Fixed Price Future (product 6590399) |
| Nodal Exchange | **AAV** | 1 MW | ISONE `.Z.NEWHAMPSHIRE` Monthly Day-Ahead Off-Peak Power Contract |

The ICE↔Nodal pairing is not inferred from the names: it is stated in Nodal's own
DCM rule filing to the CFTC, `rule021015nodaldcm002`, which tabulates the ICE
contracts and their Nodal equivalents.

**The off-peak block is not the snowmaking window, and the mismatch is one-sided.**
ICE's specification defines the block as the average of hours ending 0100–0700
and 2400 on weekdays, and all 24 hours on weekends and NERC holidays. In local
terms the weekday block is 23:00–07:00. Snowmaking runs roughly 20:00–07:00, so
the contract covers about eight of the eleven gun-hours and puts the 20:00–23:00
evening ramp — when the wet bulb has just crossed the threshold and the decision
has just been taken — inside the *peak* block instead. Any premium the contract
could carry is therefore a diluted one. That biases toward finding nothing, which
is the safe direction, but it is a real limit on what a positive result could
have meant.

## 3. Why open interest is the first question and not a preliminary

A futures test needs a settlement series. Every one of these contracts has one,
published daily, going back years. It would fit into a panel without complaint.

It would also be, for most of those months, a number the exchange wrote down
rather than a number anybody traded. Cleared power futures at zonal locations
settle by exchange mark when there is no trade, from broker submissions and curve
interpolation off the liquid hub. Regressing a wet-bulb index on a series like
that does not test whether the market prices snowmaking. It tests whether the
exchange's curve-builder interpolates through it, and the answer to that is known
in advance and is "no", because the interpolation is a basis spread off Mass Hub
that nothing in the weather enters.

So open interest is not a data-quality preliminary to the real test. It *is* the
test of whether the real test exists.

## 4. Where the number comes from, and why not from the exchanges

None of the three exchanges will serve their own per-contract open interest to
this study:

- **CME** prohibits automated access in its website Data Terms of Use and answers
  HTTP 403 with that text; a browser render returns a bot-challenge page. No
  attempt was made to work around either. CME's figures are therefore absent from
  this analysis by their choice, and that is stated rather than papered over.
- **ICE** serves the product specification freely — §2's block definition is taken
  from it — but puts its market-data endpoints behind Cloudflare.
- **Nodal** puts its end-of-day volume and open interest files behind a captcha.

The **CFTC Commitments of Traders** is the regulator's own publication of
exchange-reported open interest, is public domain, and is redistributable. It is
the only open source for this, and it turns out to be the *better* source anyway,
because it covers all three venues on one definition and reaches back sixteen
years.

    https://www.cftc.gov/files/dea/history/fut_disagg_txt_{YEAR}.zip

## 5. What absence from the COT means, stated precisely before the result

This is the part it would be easy to overclaim, so it is written down first.

The CFTC publishes a market in the COT when **20 or more traders** hold positions
at or above the reporting level for that commodity. The reporting level is set by
**17 CFR 15.03(b)**. Electricity is not named anywhere in its table, so it falls
under the catch-all row, *All Other Commodities* = **25 contracts**.

A market missing from the COT is therefore **not** a market with zero open
interest. It is a market in which **fewer than twenty traders hold twenty-five
lots or more**. Everything below is that claim and not the stronger one.

On CME's 5 MW contract twenty-five lots is 125 MW of off-peak block. On the ICE
and Nodal 1 MW contracts it is 25 MW.

## 6. Result

### 6.1 New Hampshire has never appeared, on any venue, in sixteen years

Zero rows, 2010 through 2025, across CME, ICE, ICE OTC and Nodal.

### 6.2 Which ISO-NE locations do clear the bar

| location | off-peak markets | venues | peak OI (lots) |
| --- | --- | --- | --- |
| **Mass Hub / Internal Hub** | 7 | CME, ICE, Nodal | **3,078,747** |
| **Connecticut** | 2 | CME, ICE | **672,838** |
| Maine | 0 | — | 0 |
| Vermont *(no contract listed)* | 0 | — | 0 |
| **New Hampshire** | **0** | **—** | **0** |
| NEMA / Boston | 0 | — | 0 |
| WC Mass | 0 | — | 0 |
| SE Mass | 0 | — | 0 |
| Rhode Island *(no contract listed)* | 0 | — | 0 |

Two of those zeros are the uninteresting kind. Vermont and Rhode Island have no
listed contract on ICE or Nodal at all (§1), so their absence from the COT says
only that you cannot hold what nobody sells. The other five zeros — New
Hampshire, Maine, NEMA and the two Massachusetts zones — are the informative
kind: the contract is listed on three venues and still nobody holds twenty-five
lots of it in reportable size.

**Connecticut is the row that carries the argument.** Without it the finding
would be the uninteresting one that zonal power contracts are never liquid
anywhere. Connecticut's off-peak zonal contract cleared the bar on two venues and
peaked at 672,838 lots. A zone *can* support a reportable off-peak market. Six of
the eight, New Hampshire among them, never have.

The hub is alive today and is not a historical artifact: the ICE Mass Hub
day-ahead off-peak contract stood at 73,668 lots at the end of 2025 and Nodal's
Internal Hub off-peak at 79,667. The liquidity exists. It sits at the hub.

### 6.3 CME has had no electricity market of any kind in the COT since 2018

Electricity markets meeting the COT bar, by venue:

| year | CME / NYMEX | ICE | Nodal | of which ISO-NE at CME |
| --- | --- | --- | --- | --- |
| 2010 | **32** | 0 | 0 | 6 |
| 2011 | **33** | 0 *(+4 OTC)* | 0 | 6 |
| 2012 | 28 | 4 *(+4 OTC)* | 0 | 4 |
| 2013 | 30 | 66 | 15 | 3 |
| 2014 | 21 | 98 | 24 | 2 |
| 2015 | 12 | 66 | 25 | **0** |
| 2016 | 6 | 72 | 25 | 0 |
| 2017 | 2 | 70 | 25 | 0 |
| 2018 | 1 | 58 | 26 | 0 |
| 2019 | **0** | 49 | 34 | 0 |
| 2025 | **0** | 61 | 52 | 0 |

CME's ISO-NE off-peak book was not small once. `ISO NEW ENG HUB OFF PEAK SWAP`
peaked at 1,256,026 lots and its Connecticut zonal sibling at 672,838. Both were
gone from the report by 2015, and the whole CME electricity complex by 2019. The
franchise moved to ICE and Nodal.

So the specific question — *CME New Hampshire off-peak open interest* — has an
answer in two parts. CME still publishes a product page for AU3, so the contract
appears to remain listed. But CME has had no CFTC-reportable electricity market
of any kind for seven years, and the New Hampshire zone has never had one on any
venue in sixteen. There is nothing on CME to run a futures test against.

### 6.4 The load, priced in lots of the contract that would hedge it

Off-peak hours from 1 November to 31 March, on the contract's own block
definition, are **1,960**. Against the root `README.md` §8.8 figure of 22–54 GWh
of New Hampshire snowmaking per season:

| | |
| --- | --- |
| snowmaking, spread flat across the off-peak block | **11.2–27.6 MW** |
| as a share of NH winter overnight load (~1.25 GW) | 0.9–2.2 % |
| in CME AU3 lots (5 MW) | **2.2–5.5 lots** |
| in ICE IHD / Nodal AAV lots (1 MW) | 11.2–27.6 lots |
| one reportable position, CME | 125 MW (25 lots) |
| one reportable position, ICE / Nodal | 25 MW (25 lots) |
| **the load, as a multiple of one CME reportable position** | **0.09–0.22×** |
| the load, as a multiple of one ICE / Nodal position | 0.45–1.10× |

The whole of New Hampshire's snowmaking, averaged across the block the contract
settles on, is **between a tenth and a fifth of a single reportable position** on
CME. The COT needs twenty traders holding that much before it prints a line.
Nobody is going to assemble twenty such traders around a load this size, and the
sixteen years of zeros say nobody has.

Concentrating the same energy into the ~45 productive nights of a real season
rather than spreading it flat raises the nightly figure to roughly 61–150 MW,
which is **0.49–1.20 reportable positions** — around one, rather than a tenth of
one. That is the framing favourable to the instrument and it still leaves the
entire state's snowmaking load at roughly one trader's reportable position
against the twenty the report requires, which is why both framings are given and
why neither changes the conclusion.

## 7. Verdict

**The futures leg cannot be run on New Hampshire, and the reason is not a data
problem that money or patience would fix.** The contract exists on three venues.
It has never, on any of them, had twenty traders holding twenty-five lots. Its
settlement series in most months is an exchange mark interpolated off Mass Hub,
and a wet-bulb regression on that series would be measuring the interpolation.

This is a negative result about the instrument, not about the hypothesis. It says
the New Hampshire snowmaking load is too small to have organised a market around
itself — which is the same order of finding as §8.8c's, arrived at from the other
side. §8.8c said those overnight megawatts are worth almost nothing in the spot
auction. This says nobody has ever bothered to hedge them.

## 8. Limitations

1. **The bound is "fewer than 20 traders at 25 lots", not "zero open interest".**
   The COT publication rule is a trader-count threshold. A New Hampshire off-peak
   contract with real but concentrated open interest — five traders holding a
   thousand lots each — would be invisible here and would be perfectly tradable.
   Nothing in the open record rules that out. What makes it implausible is §6.4:
   the underlying load is a fraction of one reportable position, so the
   concentrated-holder story would require a position many times the physical
   exposure it is supposed to hedge.
2. **CME's own figures are absent by CME's choice**, per §4. If AU3 carries
   open interest below the COT bar, CME knows the number and this study does not.
   A subscriber to CME DataMine could settle §6.3's first sentence properly.
3. **Listing status for AU3 is inferred from a live product page**, not from the
   NYMEX rulebook chapter, which is on a host that will not serve automated
   requests. The contract may be listed-but-dormant, a category CME maintains for
   years.
4. **The off-peak block misses the evening ramp**, per §2. The instrument was
   never well matched to the treatment even if it had been liquid.
5. **`.Z.NEMHAMPSHIRE` is a load zone, not the mountains.** Every zonal criticism
   in `src/vermont/README.md` §7 applies here and with more force, because New
   Hampshire's zone contains Manchester and Nashua as well as the White
   Mountains.
6. **Sixteen years is the COT window used here, not the contract's life.**
   The files run back further; 2010 was chosen because it precedes CME's ISO-NE
   peak and so cannot truncate the decline documented in §6.3.

## 9. Run it

```
python src/futures/cot_oi.py              # fetch (cached) + tabulate
python src/futures/cot_oi.py --no-fetch   # rebuild from cache only
```

Writes `data/futures_isone_oi.csv` (every ISO-NE market-week found, 3,632 rows)
and `data/futures_venue_census.csv`. The cache is `cache/cot/`, about 30 MB for
sixteen years, and the script is resumable — a failed year is skipped and refetched
on the next run.
