#!/usr/bin/env Rscript
# charts.R — the paper's four figures, built in R with ggplot2 + ggiraph.
#
# Each figure is written to site/fig/<name>.svg as an interactive SVG: hovering
# a mark highlights it and shows its exact value in a tooltip. site/build.py
# inlines these into the single-file page.
#
#   Rscript site/charts.R
#
# All numbers come from src/apg_pipeline.py. They are hard-coded here for the
# same reason the Python generators hard-coded them: the figure must rebuild
# without a network round trip. Rerun the pipeline to verify them.
#
# Colours are the categorical slots checked with the dataviz palette validator
# against this page's surfaces; they pass the lightness band, chroma floor and
# colour-vision separation in both modes.
#
# INK, MUT and RULE below are the LIGHT-mode values, and they are placeholders.
# ggiraph writes them into the SVG as hex presentation attributes, so site/
# build.py substitutes each one for a CSS custom property when it inlines the
# figure, and the figures then follow the page's light/dark toggle. Keep these
# three values in sync with the _SVG_TOKENS table in build.py: they are matched
# by exact uppercase hex, so changing one here without changing it there leaves
# that element stuck in light mode. The series hues are deliberately not
# substituted, so a bar keeps its identity in both themes.

suppressPackageStartupMessages({
  library(ggplot2)
  library(ggiraph)
})

# Run from the repository root: Rscript site/charts.R
OUT <- "site/fig"
if (!dir.exists(OUT)) dir.create(OUT, recursive = TRUE)

C1 <- "#2a78d6"   # blue    - default series
C2 <- "#eb6834"   # orange  - the mark the argument turns on
C3 <- "#1baf7a"   # aqua    - the pre-registered coefficient
NEU <- "#8a8a8a"  # neutral - not a series colour
INK <- "#0a0a0a"
MUT <- "#5a5a5a"
RULE <- "#e5e5e5"

base <- theme_minimal(base_size = 12, base_family = "sans") +
  theme(
    panel.grid.minor = element_blank(),
    panel.grid.major.x = element_blank(),
    panel.grid.major.y = element_line(colour = RULE, linewidth = 0.4),
    axis.title = element_text(colour = MUT, size = 9.5),
    axis.text = element_text(colour = MUT, size = 9),
    plot.background = element_rect(fill = "transparent", colour = NA),
    panel.background = element_rect(fill = "transparent", colour = NA),
    legend.position = "none",
    plot.margin = margin(10, 12, 6, 6)
  )

write_fig <- function(gg, file, w = 7.2, h = 3.5) {
  g <- girafe(
    ggobj = gg, width_svg = w, height_svg = h,
    options = list(
      opts_hover(css = "stroke-width:2.4;"),
      opts_hover_inv(css = "opacity:0.28;"),
      opts_tooltip(
        css = paste0("background:#0a0a0a;color:#fff;padding:6px 9px;",
                     "border-radius:6px;font-family:system-ui,sans-serif;",
                     "font-size:12px;"),
        opacity = 0.98),
      opts_toolbar(saveaspng = FALSE),
      opts_sizing(rescale = TRUE)
    )
  )
  # selfcontained = FALSE on purpose: it emits the widget HTML alongside a
  # shared dependency folder, so build.py can inline ggiraph's JavaScript once
  # for the whole page instead of once per figure. It also avoids a pandoc
  # dependency. The published page still makes no external request.
  htmlwidgets::saveWidget(g, file.path(normalizePath(OUT), file),
                          selfcontained = FALSE)
  cat("wrote", file, "\n")
}

# ---- Figure 2: night forecast error by month -------------------------------
months <- factor(month.abb, levels = month.abb)
m <- data.frame(
  month = months,
  bias = c(108, 21, 8, -30, -30, 8, -65, 25, -14, 70, 131, -10),
  se   = c(24, 16, 14, 16, 15, 14, 13, 16, 20, 16, 22, 30)
)
m$fill <- ifelse(m$month == "Nov", C2, C1)
m$tip <- sprintf("%s: %+d ± %d MW", m$month, m$bias, m$se)

g_month <- ggplot(m, aes(month, bias, fill = I(fill))) +
  geom_col_interactive(aes(tooltip = tip, data_id = month), width = 0.62) +
  geom_errorbar(aes(ymin = bias - se, ymax = bias + se), width = 0,
                linewidth = 0.6, colour = INK, alpha = 0.75) +
  geom_hline(yintercept = 0, colour = INK, linewidth = 0.45) +
  annotate("text", x = 11, y = 131 + 22 + 13, label = "+131",
           size = 3.6, fontface = "bold", colour = INK) +
  labs(x = NULL, y = "Night forecast error (MW)") + base
write_fig(g_month, "month.html")

# ---- Figure 3: the same error in 10-day bins -------------------------------
lab <- c("Nov\n1-10", "Nov\n11-20", "Nov\n21-30",
         "Dec\n1-10", "Dec\n11-20", "Dec\n21-30")
b <- data.frame(
  bin = factor(lab, levels = lab),
  bias = c(80, 90, 223, 223, 134, -383),
  se   = c(25, 37, 48, 41, 47, 54)
)
b$fill <- ifelse(b$bias > 150, C2, ifelse(b$bias < 0, NEU, C1))
b$tip <- sprintf("%s: %+d ± %d MW", gsub("\n", " ", b$bin), b$bias, b$se)

g_bins <- ggplot(b, aes(bin, bias, fill = I(fill))) +
  geom_col_interactive(aes(tooltip = tip, data_id = bin), width = 0.62) +
  geom_errorbar(aes(ymin = bias - se, ymax = bias + se), width = 0,
                linewidth = 0.6, colour = INK, alpha = 0.75) +
  geom_hline(yintercept = 0, colour = INK, linewidth = 0.45) +
  annotate("text", x = 4, y = 223 + 41 + 16, label = "+223",
           size = 3.6, fontface = "bold", colour = INK) +
  annotate("text", x = 6, y = -383 - 54 - 20, label = "-383",
           size = 3.6, fontface = "bold", colour = INK) +
  labs(x = NULL, y = "Night forecast error (MW)") + base
write_fig(g_bins, "bins.html", h = 3.7)

# ---- Figure 4: the coefficients --------------------------------------------
terms <- c("below × cum100\n(PRE-REGISTERED)", "below",
           "campaign start", "holiday (Christmas)")
co <- data.frame(
  term = factor(terms, levels = rev(terms)),
  est  = c(5.1, 27.2, 6.3, -273.6),
  se   = c(11.9, 53.2, 58.6, 84.0)
)
co$col <- c(C3, NEU, NEU, C2)
co$lo <- co$est - 1.96 * co$se
co$hi <- co$est + 1.96 * co$se
co$tip <- sprintf("%s: %+.1f MW (s.e. %.1f), 95%% CI [%+.0f, %+.0f]",
                  gsub("\n", " ", co$term), co$est, co$se, co$lo, co$hi)

g_coef <- ggplot(co, aes(y = term, x = est)) +
  geom_vline(xintercept = 0, linetype = "22", colour = INK, linewidth = 0.5) +
  geom_errorbarh(aes(xmin = lo, xmax = hi), height = 0, linewidth = 0.85,
                 colour = INK, alpha = 0.8) +
  geom_point_interactive(aes(tooltip = tip, data_id = term, fill = I(col)),
                         size = 4.2, shape = 21, colour = "white",
                         stroke = 1.1) +
  geom_text(aes(label = sprintf("%+.1f", est)), hjust = -0.45, vjust = -1.0,
            size = 3.3, fontface = "bold", colour = INK) +
  labs(x = "Coefficient (MW), 95% confidence interval", y = NULL) +
  base + theme(panel.grid.major.y = element_blank(),
               panel.grid.major.x = element_line(colour = RULE,
                                                 linewidth = 0.4),
               axis.text.y = element_text(colour = INK, size = 9, hjust = 1))
write_fig(g_coef, "coefs.html", h = 2.9)

# ---- Figure 1: minimum detectable effect ------------------------------------
mde <- function(ns, sd) 2.80 * sd * sqrt(0.7 + 0.3 / 8) * sqrt(2 / (ns * 9 / 2))
sc <- data.frame(
  name = c("MAE 1.5% (optimistic)", "MAE 3.14% (DE-LU)",
           "MAE 6.48% (measured AT)"),
  sd = c(132, 275, 568), col = c(C1, C2, C3)
)
d <- do.call(rbind, lapply(seq_len(nrow(sc)), function(i) data.frame(
  seasons = 2:12, name = sc$name[i], col = sc$col[i],
  y = mde(2:12, sc$sd[i]))))
d$tip <- sprintf("%s · %d seasons: %.0f MW", d$name, d$seasons, d$y)

g_mde <- ggplot(d, aes(seasons, y, colour = I(col), group = name)) +
  geom_hline(yintercept = c(90, 225, 450), linetype = "42",
             colour = MUT, linewidth = 0.45) +
  annotate("text", x = 12, y = c(90, 225, 450) + 22, hjust = 1, size = 2.9,
           colour = MUT,
           label = c("90 MW · a tenth unmodelled",
                     "225 MW · a quarter", "450 MW · half")) +
  geom_line_interactive(aes(tooltip = tip, data_id = name), linewidth = 0.9) +
  geom_point_interactive(aes(tooltip = tip, data_id = name), size = 1.7) +
  geom_text(data = subset(d, seasons == 12),
            aes(label = name), hjust = 1.02, vjust = -1.1, size = 2.9,
            show.legend = FALSE) +
  scale_x_continuous(breaks = seq(2, 12, 2)) +
  labs(x = "Seasons of data", y = "Minimum detectable effect (MW)") + base
write_fig(g_mde, "mde.html", h = 3.4)

cat("all figures written to", OUT, "\n")
