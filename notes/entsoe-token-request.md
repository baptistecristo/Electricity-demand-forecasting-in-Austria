# ENTSO-E API token — what to send

Free. Approval is documented as taking about three working days, so this was
treated as the long pole. In practice the token arrived the same day.

> **STATUS: token obtained and verified 10 August 2026.** It lives in `.env`,
> which `.gitignore` covers, and is read as `ENTSOE_TOKEN`. It is not in any
> tracked file and must not be. The verified endpoints are recorded at the bottom
> of this file.

## Step 1 — register

<https://transparency.entsoe.eu/> → create an account with the email you want the
token tied to.

## Step 2 — email

**To:** transparency@entsoe.eu
**Subject:** `RESTful API access`

---

Hello,

I would like to request RESTful API access for the Transparency Platform.

Registered email address: baptistecristofari@gmail.com

I am carrying out academic research on the accuracy of day-ahead total load
forecasts, specifically whether large weather-triggered industrial loads are
systematically under-predicted and whether that shows up in imbalance. The series
I need are:

  - Actual Total Load [6.1.A]
  - Day-Ahead Total Load Forecast [6.1.B]
  - Day-Ahead Prices [12.1.D]
  - Imbalance Prices [17.1.F]
  - Total Imbalance Volumes [17.1.G]

for the AT bidding zone, with CH, IT-North, NL and DK as controls.

Thank you,
Baptiste Cristofari

---

## Step 3 — generate the token

Once the approval email arrives: log in → **My Account** → **Web Api Security
Token** → generate.

Then:

```bash
export ENTSOE_TOKEN=<paste>
```

## Why the imbalance series were added to the request

The load test and the day-ahead price test both close at the same moment: APG
publishes its forecast at 08:00 on D-1 and the day-ahead auction clears around
noon. A weather-forecast revision arriving *after* noon is information a resort
acts on and neither the forecast nor the day-ahead price can contain. Whatever
that produces has nowhere to go but imbalance. §9 of the root README lists
imbalance as the untried instrument, and these two series are what it needs.

## Optional — worth asking APG at the same time

The single biggest unknown in this design is how much of the snowmaking load the
day-ahead forecast already absorbs (README §3, the α parameter). That depends on
whether APG's forecast is a temperature-and-calendar regression or an
autoregressive/ML model using lagged actual load.

APG's transparency page lists the inputs but not the functional form. Forecasting
teams often answer this directly. Suggested note to their transparency contact:

> I am researching day-ahead load forecast accuracy in the APG control area for
> an academic project. Your transparency page lists the forecast inputs as
> historical load, day type and temperature forecast. Could you say whether the
> model uses lagged actual load autoregressively, and roughly what class of model
> it is (linear regression, gradient boosting, neural network)? I am not asking
> for anything proprietary — just enough to characterise whether the model has
> memory of recent load.

A "yes, it's autoregressive" answer materially lowers the expected effect size
and is worth knowing before spending two weeks on the wet-bulb index.


---

## Verified endpoints, 10 August 2026

All probed with `periodStart=202312010000&periodEnd=202312020000`. Zone EICs:
AT `10YAT-APG------L`, CH `10YCH-SWISSGRIDZ`, NL `10YNL----------L`,
DK1 `10YDK-1--------W`, IT-North `10Y1001A1001A73I`.

| series | params | result |
| --- | --- | --- |
| Day-ahead load forecast | `documentType=A65&processType=A01&outBiddingZone_Domain=` | 200, 94 points |
| Actual load | `documentType=A65&processType=A16&outBiddingZone_Domain=` | 200, 96 points |
| Day-ahead price | `documentType=A44&in_Domain=&out_Domain=` | 200, works |
| **Imbalance prices** | `documentType=A85&controlArea_Domain=` | 200, **190 points, PT15M** |
| **Total imbalance volumes** | `documentType=A86&controlArea_Domain=` | 200, **96 points, PT15M**, flowDirection A01/A02 |
| NL / DK1 / IT-North load forecast | as above with their EICs | 200, all serve |

**The trap: A85 and A86 return a ZIP, not XML.** The body starts with `PK`, and a
parser that regexes the response text for `<quantity>` finds nothing and reports
the series as empty when the data is there. Unzip first; the archive holds one
file, `001-IMBALANCE_PRICES_R3_<start>-<end>.xml` or
`001-TOTAL_IMBALANCE_VOLUMES_R3_...`. The load and price endpoints return plain
XML, so the same code path does not work for both.

**Why imbalance matters here.** ISO-NE's day-ahead market closes at 10:30 ET and
APG publishes at 08:00 on D-1. A weather-forecast revision arriving after those
gates is information an operator acts on and neither the load forecast nor the
day-ahead price can contain. Imbalance is the only place it can land, and at
PT15M it is the finest-grained outcome available anywhere in this project.
