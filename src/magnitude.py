"""
Magnitude check for Austrian snowmaking as a coincident power load.
Source figures: Aigner, Steiger & Mayer (2026), "Snowmaking in Austria:
resource consumption and greenhouse gas emissions", J. Sustainable Tourism.
Survey of 141 resorts, 30 usable, 4,253 ha equipped = 34.0% of Austrian volume.
"""
import numpy as np

# --- published figures -------------------------------------------------
E_central = 281.0          # GWh per season, Austria-wide extrapolation
E_lo, E_hi = 260.0, 309.0  # GWh, reported range
hours_per_gun = 184.6      # average operating hours per snowmaker per season
guns_per_ha = 2.9
kwh_per_ha_sample = 22449.0   # CISS version (sample, equipped ha)
kwh_per_ha_alt = 18378.0      # alt figure quoted (per ha of slopes)
kwh_per_m3 = 3.3
share_of_AT_electricity = 0.0046   # 0.46%

AT_annual_TWh = E_central / 1000 / share_of_AT_electricity
AT_avg_load_GW = AT_annual_TWh * 1000 / 8.760 / 1000

print(f"Implied Austrian annual electricity consumption: {AT_annual_TWh:.1f} TWh")
print(f"Implied Austrian average load:                   {AT_avg_load_GW:.2f} GW\n")

# --- per-gun sanity check ----------------------------------------------
kwh_per_gun_season = kwh_per_ha_sample / guns_per_ha
kw_per_gun = kwh_per_gun_season / hours_per_gun
print("Per-gun consistency check")
print(f"  energy per gun per season : {kwh_per_gun_season:,.0f} kWh")
print(f"  mean draw while operating : {kw_per_gun:.1f} kW  "
      f"(plausible: lance ~5-15 kW, fan gun ~20-40 kW, + pumping/air)\n")

# --- fleet-wide fully-coincident ceiling --------------------------------
# If every snowmaker in Austria ran simultaneously, aggregate draw is simply
# season energy / average operating hours per gun.
for name, E in [("low", E_lo), ("central", E_central), ("high", E_hi)]:
    P = E / hours_per_gun     # GWh / h = GW
    print(f"Fleet-wide coincident ceiling ({name:<7} {E:.0f} GWh): {P:.2f} GW")

P_ceiling = E_central / hours_per_gun
print()

# --- realistic coincidence ----------------------------------------------
# Not every gun runs at once: altitude spread, staggered opening dates,
# water reservoir and compressed-air capacity limits, crew availability.
print("Aggregate national draw at different coincidence factors "
      f"(ceiling {P_ceiling:.2f} GW):")
for cf in [0.3, 0.4, 0.5, 0.6, 0.7, 0.8]:
    print(f"  coincidence {cf:.0%} -> {P_ceiling*cf:.2f} GW")
print()

# --- as a share of overnight Austrian load ------------------------------
# Winter overnight trough (01:00-05:00, Nov-Dec) for the APG control area.
for night_load in [5.5, 6.0, 6.5, 7.0]:
    lo = P_ceiling * 0.4 / night_load
    hi = P_ceiling * 0.7 / night_load
    print(f"Overnight load {night_load:.1f} GW -> snowmaking is "
          f"{lo:.1%} to {hi:.1%} of it")
print()

# --- how many usable hours actually exist -------------------------------
# 184.6 h is per GUN, not the number of hours in which SOME gun is running.
# The season-wide window in which aggregate snowmaking is materially non-zero
# is larger. Bound it: total gun-hours / typical simultaneous fraction.
national_ha = 4253 / 0.34
n_guns = national_ha * guns_per_ha
gun_hours = n_guns * hours_per_gun
print(f"National equipped area (extrapolated): {national_ha:,.0f} ha")
print(f"National snowmaker count (implied):    {n_guns:,.0f}")
print(f"Total gun-hours per season:            {gun_hours/1e6:.2f} million")
for cf in [0.4, 0.6, 0.8]:
    hrs = gun_hours / (n_guns * cf)
    print(f"  at {cf:.0%} average coincidence -> "
          f"{hrs:.0f} calendar hours per season with snowmaking running")
