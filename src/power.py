"""
Detectability calculation for the snowmaking-in-load-forecast-error test.

Question: given how few snowmaking episodes exist per season and how much of
the load the day-ahead forecast absorbs anyway, how many seasons of ENTSO-E
data does the threshold test need before it can see anything?

Error scale is anchored on a measured figure: for the DE-LU zone the TSO
day-ahead load forecast MAE is 3.14% of mean load over 2016-2019 ENTSO-E TP
data (arXiv 2302.11017). AT is a smaller zone, so relative error is likely
worse, not better. MAE is converted to sd assuming near-normal errors
(sd = MAE / 0.7979).
"""
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

# ---- design constants --------------------------------------------------
EPISODES_PER_SEASON = 9      # distinct Nov-Dec cold snaps that trigger snowmaking
HOURS_PER_EPISODE   = 8      # night hours (22:00-06:00) per episode
RHO                 = 0.7    # within-episode correlation of forecast residuals
Z                   = 2.80   # z_{0.975} + z_{0.80}

NIGHT_LOAD_MW = 7000         # AT weekday Nov-Dec overnight load, 01:00-05:00
MAE_TO_SD = 1 / 0.7979

SCENARIOS = {                       # label -> day-ahead forecast MAE, % of load
    "optimistic, MAE 1.5%":          0.015,
    "DE-LU measured, MAE 3.14%":     0.0314,
    "small-zone penalty, MAE 5%":    0.050,
}

S_MW = 900                   # coincident snowmaking load on a campaign night


def episode_sd(sigma_hourly, hours=HOURS_PER_EPISODE, rho=RHO):
    """SD of the mean residual over one autocorrelated episode."""
    return sigma_hourly * np.sqrt(rho + (1 - rho) / hours)


def mde(seasons, sigma_hourly, treat_share=0.5):
    """Minimum detectable difference in MW between just-below and just-above
    threshold episodes, 80% power / 5% two-sided."""
    n = seasons * EPISODES_PER_SEASON
    n_t, n_c = n * treat_share, n * (1 - treat_share)
    se = episode_sd(sigma_hourly) * np.sqrt(1 / n_t + 1 / n_c)
    return Z * se


seasons = np.arange(1, 13)

print(f"Overnight load assumed: {NIGHT_LOAD_MW} MW")
print(f"Coincident snowmaking load on a campaign night: {S_MW} MW")
print(f"Episodes/season {EPISODES_PER_SEASON}, hours/episode {HOURS_PER_EPISODE}, rho {RHO}\n")
print("Residual signal = alpha * S, where alpha is the share the day-ahead")
print("forecast has NOT already absorbed via its temperature coefficient and")
print("lagged-load terms:\n")
for a in (0.10, 0.25, 0.50):
    print(f"   alpha {a:>4.0%}  ->  signal {a*S_MW:>4.0f} MW")
print()

fig, ax = plt.subplots(figsize=(10, 6))
colors = ["#2b6cb0", "#c05621", "#702459"]

for (label, mae_pct), c in zip(SCENARIOS.items(), colors):
    sd = mae_pct * MAE_TO_SD * NIGHT_LOAD_MW
    y = [mde(s, sd) for s in seasons]
    ax.plot(seasons, y, "-o", color=c, ms=4, lw=1.8,
            label=f"{label}  (sd {sd:.0f} MW)")
    print(f"{label:<28} sd={sd:6.0f} MW   MDE  4 seasons={mde(4,sd):5.0f}   "
          f"7={mde(7,sd):5.0f}   12={mde(12,sd):5.0f} MW   "
          f"| alpha needed at 7 seasons: {mde(7,sd)/S_MW:5.1%}")

for a, ls, lab in [(0.50, "-", "half the load unmodelled"),
                   (0.25, "--", "quarter unmodelled"),
                   (0.10, ":", "tenth unmodelled")]:
    ax.axhline(a * S_MW, color="#276749", ls=ls, lw=1.4, alpha=0.85)
    ax.text(12.1, a * S_MW, f"  {a*S_MW:.0f} MW\n  {lab}",
            va="center", fontsize=8, color="#276749")

ax.axvspan(7.5, 12, color="#f2f2f2", zorder=0)
ax.text(9.75, 25, "beyond the clean AT bidding zone\n(split 1 Oct 2018)",
        ha="center", fontsize=8, color="#777", zorder=1)

ax.set_xlabel("Seasons of data")
ax.set_ylabel("Minimum detectable effect (MW)")
ax.set_title("Can the threshold test see snowmaking?\n"
             "MDE vs plausible residual signal, 80% power / 5% two-sided",
             fontsize=12, loc="left")
ax.set_xlim(1, 12); ax.set_ylim(0, 500)
ax.grid(alpha=0.25)
ax.legend(loc="upper right", fontsize=9, frameon=False)
fig.tight_layout()
fig.savefig("figures/detectability.png", dpi=160)
print("\nsaved figures/detectability.png")
