# =============================================================================
# export_dashboard.R
# One data file for the NDVI outlook dashboard, for ONE issue date: every cropland grid cell with its forecasts,
# observations, normal and crop calendar. Regions (full domain, East, West, South Africa, ...) are boxes inside
# the dashboard, so the file always holds the full domain (or a test box with --box).
# Random forest models only (no LASSO, no per-grid-cell MLR).
#
# MONTHS (issue T, initial condition t = T - 1): t-2 ... lead 3 + 2, i.e. 8 months (Jul-Feb for a 1 Oct issue)
#   observed SA      t-2 ... t                  (harmonized NDVI)
#   forecast SA      leads 1-3 (T ... T+2)      (08c: forecasts/forecast_<T>_long.rds)
#   normal           mean, SD (SA definition) and 5th-95th percentiles of NDVI 2003-2025, as Figure 4c
#   crop calendar    one string per crop over the 8 months: P early (planting-vegetative), G mid (vegetative-harvest),
#                    H late (harvest-end of season), . outside the season (load_meta(), identify_season_months())
#
# FILE  dashboard_data/ndvi_dashboard_<T>.json
#   issue, ic_month, months[8], obs_months[3], lead_months[3], models[{id, label, desc, n}], cells[]
#   cell: lon, lat, c (country), ai (aridity class), cr (crops), mu[8], sd[8], p05[8], p95[8],
#         o[3] (observed SA), f{model id: [3] SA}, cal{crop: "8 letters"}
#   a model without a forecast for a grid cell is absent from its f
#         u1, u2 (HarvestStat admin 1 and admin 2 unit of the grid cell centre; c = HarvestStat ADMIN0 when found)
#   outline{x, y}: country outlines for the map (maps package, full domain), polygons separated by null
#   units[]: HarvestStat units (simplified by --simplify degrees): a0, a1, a2 names, label point lx, ly, rings x, y
#            separated by null
#
# NEEDS  ../5_paper/utils_paper.R (same loaders and SA as Figure 4), 08c forecast of the issue, packages jsonlite, maps, sf
#        HarvestStat boundaries (F_UNITS, as Figure 4); without them the units are left out
# RUN    cd src/ndvi_dashboard
#        Rscript export_dashboard.R --issue=2026-10-01
#        Rscript export_dashboard.R --issue=2026-10-01 --box=22,55,-12,23        (lon1,lon2,lat1,lat2: small test file)
#        --simplify=0.01   tolerance (degrees) of the HarvestStat boundaries (larger = smaller file)
# =============================================================================

.sd <- (function() { a <- commandArgs(FALSE); f <- sub("^--file=", "", a[grep("^--file=", a)])
  if (length(f) == 1) dirname(normalizePath(f)) else getwd() })()
MODEL_SET <- "rf"
source(file.path(.sd, "..", "5_paper", "utils_paper.R"), chdir = TRUE)

# ---- INPUT BLOCK ----
ARGS  <- commandArgs(TRUE); ga <- function(n, d) { h <- grep(paste0("^--", n, "="), ARGS, value = TRUE); if (length(h)) sub(".*=", "", h[1]) else d }
ISSUE <- format(as.Date(ga("issue", "2026-10-01")), "%Y-%m-01")
BOX   <- as.numeric(strsplit(ga("box", "-180,180,-90,90"), ",")[[1]])     # lon1, lon2, lat1, lat2
CLIM_YEARS <- 2003:2025
LEADS <- c(0, 1, 2)                                                      # leads 1-3
# dashboard id = 08c model name; label and description shown in the dashboard menu, in this order
MODELS <- data.frame(
  id    = c("smap", "fsc", "fsm", "ndvi"),
  model = c("rf_smap_climate_smf_smapera", "rf_fldas_sm_climate_smf", "rf_fldas_sm", "rf_ndvi"),
  label = c("SMAP–FLDAS*", "FLDAS SM + climate", "FLDAS SM", "NDVI ONLY"),
  desc  = c("NDVI + SMAP SM + FLDAS P, T IC + FLDAS SM Forecast", "NDVI + FLDAS SM IC + FLDAS P, T IC + FLDAS SM Forecast",
            "NDVI + FLDAS SM IC + FLDAS SM Forecast", "Past NDVI only"), stringsAsFactors = FALSE)
CROP_FULL <- c(mill = "millet", pmil = "pearl millet", smil = "small millet", sorg = "sorghum", maiz = "maize",
               whea = "wheat", barl = "barley", rice = "rice", teff = "teff", cass = "cassava", grou = "groundnut",
               sesa = "sesame", cott = "cotton", bean = "bean", cowp = "cowpea", chic = "chickpea", soyb = "soybean",
               ocer = "other cereals", pota = "potato", swpo = "sweet potato", yams = "yams", sugc = "sugarcane")
DIR_OUT <- file.path(PATH_ROOT, "dashboard_data")
F_UNITS <- file.path(PATH_ROOT, "data", "raw", "spatial_data", "harveststat", "hvstat_africa_boundary_1.1_paper_experiment.shp")
SIMP    <- as.numeric(ga("simplify", "0.01"))                             # degrees
# ---------------------
for (p in c("jsonlite", "maps")) if (!requireNamespace(p, quietly = TRUE)) stop("needs the R package ", p)
dir.create(DIR_OUT, showWarnings = FALSE, recursive = TRUE)
crop_name_of <- function(x) { x <- tolower(x); ifelse(x %in% names(CROP_FULL), CROP_FULL[x], x) }

WIN   <- add_month(ISSUE, -3:4)                                          # the 8 months shown
ic    <- add_month(ISSUE, -1); obs_d <- add_month(ISSUE, -3:-1); tgt_d <- add_month(ISSUE, LEADS)
wm    <- as.integer(format(WIN, "%m"))
cat("Issue", ISSUE, "| initial condition", mlab(ic), "| months", mlab(WIN[1]), "-", mlab(WIN[8]), "\n")

# ---- grid cells ----
G <- load_grids() %>% filter(lon >= BOX[1], lon <= BOX[2], lat >= BOX[3], lat <= BOX[4])
ctry <- maps::map.where("world", G$lon, G$lat); G$country <- ifelse(is.na(ctry), "", sub(":.*$", "", ctry))
G$crops <- vapply(strsplit(G$crops, ",\\s*"), function(v) paste(unique(crop_name_of(v)), collapse = ", "), "")
cat("Grid cells:", nrow(G), "\n")

# ---- HarvestStat units: unit of each grid cell, simplified boundaries and label points ----
G$u1 <- ""; G$u2 <- ""; UNITS <- list()
if (file.exists(F_UNITS)) {
  suppressPackageStartupMessages(library(sf)); sf_use_s2(FALSE)
  U <- st_read(F_UNITS, quiet = TRUE); if (is.na(st_crs(U))) st_crs(U) <- 4326
  U <- st_make_valid(st_transform(U, 4326))
  cat("HarvestStat units:", nrow(U), "| columns:", paste(setdiff(names(U), attr(U, "sf_column")), collapse = ", "), "\n")
  colv <- function(cands) { h <- cands[cands %in% names(U)]
    v <- if (length(h)) as.character(U[[h[1]]]) else rep("", nrow(U)); ifelse(is.na(v), "", v) }
  U$a0 <- colv(c("ADMIN0", "admin0", "COUNTRY", "country", "NAME_0"))
  U$a1 <- colv(c("ADMIN1", "admin1", "NAME_1"))
  U$a2 <- colv(c("ADMIN2", "admin2", "NAME_2"))
  bb <- st_as_sfc(st_bbox(c(xmin = max(BOX[1], -20), xmax = min(BOX[2], 60), ymin = max(BOX[3], -40), ymax = min(BOX[4], 40)), crs = 4326))
  U <- U[lengths(st_intersects(U, bb)) > 0, ]
  # unit of each grid cell centre
  P  <- st_as_sf(G[, c("grid", "lon", "lat")], coords = c("lon", "lat"), crs = 4326, remove = FALSE)
  J  <- suppressMessages(st_join(P, U[, c("a0", "a1", "a2")], join = st_intersects, left = TRUE))
  J  <- J[!duplicated(J$grid), ]; m <- match(G$grid, J$grid)
  G$u1 <- ifelse(is.na(J$a1[m]), "", J$a1[m]); G$u2 <- ifelse(is.na(J$a2[m]), "", J$a2[m])
  G$country <- ifelse(!is.na(J$a0[m]) & nzchar(J$a0[m]), J$a0[m], G$country)
  cat("Grid cells inside a HarvestStat unit:", sum(nzchar(G$u1) | nzchar(G$u2)), "of", nrow(G), "\n")
  # simplified boundaries (rings separated by NA -> null) and one label point per unit
  Us <- suppressWarnings(st_simplify(U, dTolerance = SIMP, preserveTopology = TRUE)); Us <- Us[!st_is_empty(Us), ]
  UNITS <- Filter(Negate(is.null), lapply(seq_len(nrow(Us)), function(i) tryCatch({
    g  <- st_geometry(Us)[[i]]
    if (inherits(g, "GEOMETRYCOLLECTION")) g <- st_union(st_collection_extract(st_sfc(g, crs = 4326), "POLYGON"))[[1]]
    co <- st_coordinates(g); key <- paste(co[, "L1"], if ("L2" %in% colnames(co)) co[, "L2"] else 1)
    rg <- split(seq_len(nrow(co)), factor(key, levels = unique(key)))
    lp <- suppressWarnings(st_coordinates(st_point_on_surface(st_sfc(g, crs = 4326))))
    list(a0 = Us$a0[i], a1 = Us$a1[i], a2 = Us$a2[i], lx = round(lp[1, 1], 3), ly = round(lp[1, 2], 3),
         x = unlist(lapply(rg, function(r) c(round(co[r, "X"], 3), NA)), use.names = FALSE),
         y = unlist(lapply(rg, function(r) c(round(co[r, "Y"], 3), NA)), use.names = FALSE))
  }, error = function(e) NULL)))
  cat("HarvestStat units written:", length(UNITS), sprintf("(simplified to %g deg)\n", SIMP))
} else message("No HarvestStat boundaries at ", F_UNITS, " (units left out of the dashboard)")

# ---- normal: mean and SD (SA definition) + 5th-95th percentiles of 2003-2025 (as Figure 4c) ----
clim <- load_ndvi_clim() %>% filter(grid %in% G$grid)
hist_d <- as.Date(sprintf("%d-%02d-01", rep(CLIM_YEARS, each = 12), rep(1:12, length(CLIM_YEARS))))
hist_d <- hist_d[as.integer(format(hist_d, "%m")) %in% wm]
OB <- read_ndvi_obs(c(hist_d, obs_d)) %>% filter(grid %in% G$grid) %>% mutate(date = as.Date(date))
PQ <- OB %>% filter(as.integer(format(date, "%Y")) %in% CLIM_YEARS) %>% mutate(month = as.integer(format(date, "%m"))) %>%
  group_by(grid, month) %>% summarise(p05 = quantile(ndvi, 0.05), p95 = quantile(ndvi, 0.95), .groups = "drop")
NORM <- expand.grid(grid = G$grid, k = 1:8, stringsAsFactors = FALSE) %>% mutate(month = wm[k]) %>%
  left_join(clim, by = c("grid", "month")) %>% left_join(PQ, by = c("grid", "month")) %>% arrange(grid, k)
sa_of <- function(ndvi, grid, date) { m <- as.integer(format(as.Date(date), "%m"))
  i <- match(paste(grid, m), paste(clim$grid, clim$month)); s <- clim$clim_sd[i]
  ifelse(!is.na(s) & s >= 0.01, (ndvi - clim$clim_value[i]) / s, NA_real_) }

# ---- observed SA (t-2 ... t) ----
OS <- OB %>% filter(date %in% obs_d) %>% mutate(sa = sa_of(ndvi, grid, date), k = match(date, obs_d))
if (!any(OS$date == ic)) warning("no observed NDVI for the initial condition month ", mlab(ic))

# ---- forecasts (08c), random forest models only ----
f_fc <- file.path(PATH_FCST, sprintf("forecast_%s_long.rds", ISSUE))
if (!file.exists(f_fc)) stop("missing ", f_fc, " -> Rscript 08c_run_forecast_rf.R --issue=", ISSUE)
FC <- readRDS(f_fc) %>% filter(status == "ok", lead %in% LEADS, grepl("^rf_", model), model %in% MODELS$model) %>%
  transmute(grid = clean_id(grid_id), model, lead, date = as.Date(target_date), ndvi = ndvi_fcst_T) %>%
  filter(grid %in% G$grid) %>% mutate(sa = sa_of(ndvi, grid, date), id = MODELS$id[match(model, MODELS$model)])
miss <- setdiff(MODELS$model, unique(FC$model))
if (length(miss)) { message("no forecast in ", basename(f_fc), " for: ", paste(miss, collapse = ", "), " (left out)")
  MODELS <- MODELS[!MODELS$model %in% miss, ] }
# persistence: SA of the initial condition month kept for the three leads; climatology: SA = 0
PS <- OS %>% filter(date == ic) %>% select(grid, sa_ic = sa)

# ---- crop calendar: one string per crop over the 8 months ----
CAL <- load_meta() %>% filter(grid %in% G$grid, !is.na(planting), !is.na(vegetative), !is.na(harvest), !is.na(endofseaso)) %>%
  distinct(grid, crop_name, planting, vegetative, harvest, endofseaso)
CAL$crop <- crop_name_of(CAL$crop_name)
CAL$cal <- vapply(seq_len(nrow(CAL)), function(i) { s <- identify_season_months(CAL$planting[i], CAL$vegetative[i], CAL$harvest[i], CAL$endofseaso[i])
  paste(ifelse(wm %in% s$early, "P", ifelse(wm %in% s$mid, "G", ifelse(wm %in% s$late, "H", "."))), collapse = "") }, "")
CAL <- CAL %>% distinct(grid, crop, .keep_all = TRUE)

# ---- one record per grid cell ----
r3 <- function(x) round(x, 3); r2 <- function(x) round(x, 2)
sp <- function(d, key) split(d, d[[key]])
NS <- sp(NORM, "grid"); OSs <- sp(OS, "grid"); FCs <- sp(FC, "grid"); CALs <- sp(CAL, "grid")
cells <- lapply(seq_len(nrow(G)), function(i) { g <- G$grid[i]
  n <- NS[[g]]; o <- OSs[[g]]; f <- FCs[[g]]; cl <- CALs[[g]]
  ov <- rep(NA_real_, 3); if (!is.null(o)) ov[o$k] <- o$sa
  fl <- list()
  if (!is.null(f)) for (m in unique(f$id)) { v <- rep(NA_real_, 3); x <- f[f$id == m, ]; v[x$lead + 1] <- x$sa; fl[[m]] <- r2(v) }
  si <- PS$sa_ic[match(g, PS$grid)]; if (!is.na(si)) fl$pers <- r2(rep(si, 3))
  fl$clim <- c(0, 0, 0)
  list(lon = G$lon[i], lat = G$lat[i], c = G$country[i], u1 = G$u1[i], u2 = G$u2[i], ai = tolower(as.character(G$ai_class[i])), cr = G$crops[i],
       mu = r3(n$clim_value), sd = r3(n$clim_sd), p05 = r3(n$p05), p95 = r3(n$p95), o = r2(ov), f = fl,
       cal = if (is.null(cl)) setNames(list(), character(0)) else as.list(setNames(cl$cal, cl$crop)))
})

n_of <- function(m) format(sum(vapply(cells, function(x) !is.null(x$f[[m]]), logical(1))), big.mark = ",")
mods <- rbind(MODELS[, c("id", "label", "desc")],
              data.frame(id = c("pers", "clim"), label = c("Persistence", "Climatology"),
                         desc = c(sprintf("The %s anomaly kept for the next three months", format(as.Date(ic), "%B")),
                                  "Normal NDVI for the month (2003–2025 average)")))
mods$n <- vapply(mods$id, n_of, "")
# ---- country outlines for the map (maps package), polygons separated by NA -> null ----
OL <- maps::map("world", plot = FALSE, fill = TRUE, xlim = c(-20, 60), ylim = c(-40, 40))
OUTLINE <- list(x = round(OL$x, 2), y = round(OL$y, 2))
OUT <- list(issue = ISSUE, ic_month = format(as.Date(ic), "%Y-%m"),
            months = format(WIN, "%Y-%m"), obs_months = format(obs_d, "%Y-%m"), lead_months = format(tgt_d, "%Y-%m"),
            models = mods, cells = cells, outline = OUTLINE, units = UNITS)
F_OUT <- file.path(DIR_OUT, sprintf("ndvi_dashboard_%s%s.json", ISSUE, if (any(grepl("^--box=", ARGS))) "_box" else ""))
jsonlite::write_json(OUT, F_OUT, auto_unbox = TRUE, digits = NA, na = "null", null = "null")

# ---- checks ----
cat("Models (grid cells with a forecast):\n"); print(mods[, c("id", "label", "n")], row.names = FALSE)
cat(sprintf("Normal: %.1f%% of months with mean, %.1f%% with percentiles | observed SA at the initial condition: %d grid cells\n",
            100 * mean(!is.na(NORM$clim_value)), 100 * mean(!is.na(NORM$p05)), sum(!is.na(PS$sa_ic))))
cat("Forecast SA range:", paste(round(range(FC$sa, na.rm = TRUE), 2), collapse = " to "),
    "| grid cells with a crop calendar:", length(CALs), "\n")
cat("->", F_OUT, sprintf("(%.1f MB)\n", file.size(F_OUT) / 1e6))
