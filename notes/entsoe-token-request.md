# ENTSO-E API token — what to send

Free. Approval takes about three working days, so this is the long pole. Send it
today.

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
forecasts in the Austrian bidding zone, specifically whether large
weather-triggered industrial loads are systematically under-predicted. The series
I need are Actual Total Load [6.1.A] and Day-Ahead Total Load Forecast [6.1.B] for
the AT bidding zone, with NL and DK as controls.

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
