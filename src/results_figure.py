"""
results_figure.py — figures for README §8.

Numbers are the output of src/apg_pipeline.py (APG 2010-2022, 780 Nov-Dec
nights, 13 seasons). Hard-coded here so the figure regenerates without a network
round trip; rerun the pipeline to verify them.
"""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

BLUE, RED, GREY, GREEN = "#2b6cb0", "#c05621", "#8a8a8a", "#276749"

# --- panel A: night bias by month --------------------------------------
months = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"]
bias   = [108, 21, 7, -30, -30, 8, -65, 25, -14, 70, 131, -10]
se     = [24, 16, 14, 16, 15, 14, 13, 16, 20, 16, 22, 30]

# --- panel B: Nov 1 - Dec 30 in 10-day bins ----------------------------
bins   = ["Nov\n1-10","Nov\n11-20","Nov\n21-30","Dec\n1-10","Dec\n11-20","Dec\n21-30"]
bbias  = [80, 90, 223, 223, 134, -383]
bse    = [25, 37, 48, 41, 47, 54]

# --- panel C: coefficients, primary spec -------------------------------
terms  = ["below x cum100\n(PRE-REGISTERED)", "below", "campaign\nstart", "holiday\n(Christmas)"]
coef   = [5.1, 27.2, 6.3, -273.6]
cse    = [11.9, 53.2, 58.6, 84.0]

fig, axes = plt.subplots(1, 3, figsize=(15.5, 5.2),
                         gridspec_kw={"width_ratios": [1.15, 1, 1.15]})

ax = axes[0]
c = [RED if m == "Nov" else BLUE for m in months]
ax.bar(months, bias, yerr=se, color=c, capsize=2, error_kw={"lw": 1, "ecolor": "#444"})
ax.axhline(0, color="k", lw=0.8)
ax.set_ylabel("Night forecast error, actual − forecast (MW)")
ax.set_title("A. November is the most under-forecast\nmonth of the year",
             fontsize=11, loc="left")
ax.grid(axis="y", alpha=0.25)

ax = axes[1]
c = [RED if b > 150 else (GREY if b < 0 else BLUE) for b in bbias]
ax.bar(range(len(bins)), bbias, yerr=bse, color=c, capsize=3,
       error_kw={"lw": 1, "ecolor": "#444"})
ax.set_xticks(range(len(bins))); ax.set_xticklabels(bins, fontsize=8)
ax.axhline(0, color="k", lw=0.8)
ax.annotate("Christmas\nshutdown", xy=(5, -383), xytext=(4.0, -300),
            fontsize=8, color="#444", ha="center",
            arrowprops=dict(arrowstyle="->", lw=0.8, color="#444"))
ax.set_title("B. The seasonal hump looks like snowmaking …\n"
             "ramp, peak at opening, then decline", fontsize=11, loc="left")
ax.grid(axis="y", alpha=0.25)

ax = axes[2]
y = np.arange(len(terms))[::-1]
cols = [GREEN, GREY, GREY, RED]
ax.errorbar(coef, y, xerr=[1.96*s for s in cse], fmt="o", ms=7,
            capsize=4, lw=1.6, color="#333", ecolor="#333", zorder=3)
for yi, ci, col in zip(y, coef, cols):
    ax.plot(ci, yi, "o", ms=9, color=col, zorder=4)
ax.axvline(0, color="k", lw=0.9, ls="--")
ax.set_yticks(y); ax.set_yticklabels(terms, fontsize=9)
ax.set_xlabel("Coefficient (MW), 95% CI")
ax.set_title("C. … but conditional on weather it is zero.\n"
             "The same model still sees Christmas.", fontsize=11, loc="left")
ax.grid(axis="x", alpha=0.25)
ax.set_xlim(-480, 180)

fig.suptitle("Snowmaking is absorbed by the day-ahead forecast, not missed by it"
             "   ·   APG 2010–2022, 780 November–December nights, 13 seasons",
             fontsize=12.5, y=1.02, x=0.02, ha="left")
fig.tight_layout()
fig.savefig("figures/results.png", dpi=160, bbox_inches="tight")
print("wrote figures/results.png")
