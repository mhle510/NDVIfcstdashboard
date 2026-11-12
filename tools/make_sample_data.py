#!/usr/bin/env python3
"""
Write a SYNTHETIC data file with the same layout as export_dashboard.R, to try the dashboard
without the real forecasts:  python tools/make_sample_data.py sample/ndvi_dashboard_2026-09-01_sample.json
Values, outlines and countries are made up (schematic); never use them for anything else.
"""
import json, math, os, sys
OUT = sys.argv[1] if len(sys.argv) > 1 else "sample/ndvi_dashboard_2026-09-01_sample.json"
RES = 0.5
AF=[(-17,21),(-17.1,14.7),(-16.7,12.5),(-15,11),(-13.3,9.5),(-11.5,7),(-8,4.4),(-4,5.1),(0,5.6),(2.5,6.3),(4.5,6.2),(6,4.3),(8.5,4.5),(9.6,3),(9.5,1),(9,-1),(11.8,-4),(12.3,-6),(13.4,-9),(13.6,-12),(12.2,-15),(11.8,-17.5),(14.5,-22.5),(15.2,-27),(16.5,-28.6),(18.4,-33.9),(20,-34.8),(22.5,-34),(25.6,-34),(28,-33),(30.5,-31),(32.5,-28.5),(32.9,-26),(35.5,-24),(35.5,-21),(34.8,-19.8),(36.8,-17.8),(40.5,-15),(40.5,-10.5),(39.3,-8),(39,-5),(41.5,-1.7),(44,1.5),(47.5,5),(49.5,8),(51.2,11.8),(48,11.2),(44,10.4),(43.3,11.8),(42.6,13),(41,14.8),(39.5,15.8),(38.5,18),(37.4,20),(36.9,22),(35.5,24),(34,26.5),(32.6,29.9),(32.3,31.3),(29.9,31.2),(25,31.6),(20.1,32.2),(19,30.3),(15.4,31.5),(13,32.9),(11.1,33.2),(10.2,36.9),(9.8,37.3),(8,36.9),(3,36.8),(-1.9,35.1),(-5.9,35.8),(-6.8,34),(-9.6,30.4),(-9.8,29),(-13,27.7),(-14.5,26),(-16,23.8)]
MG=[(49.3,-12),(50.4,-15.5),(49.5,-17),(47.2,-25),(45,-25.5),(43.7,-23.5),(44.4,-20),(44,-17),(46.3,-15.7),(48,-13.5)]
ME=[(32.3,31.3),(34.2,31.3),(34.9,32.8),(35.5,34.6),(36,35.9),(36.2,36.6),(34,36.2),(32,36.1),(30.5,36.4),(28,36.7),(26.5,38.5),(26.3,40),(60,40),(60,25.3),(57,25.7),(56.3,27.2),(54,26.7),(51.5,27.9),(50.3,29.9),(48.6,30),(48,29.5),(48.8,28),(50.2,26.2),(51.6,24.6),(54.4,24.3),(56.1,26.1),(56.4,24.9),(58.6,23.6),(59.8,22.4),(57.8,19),(55,17),(52,15.8),(48.5,14),(45,12.8),(43.3,12.7),(42.8,16.3),(41.6,17.5),(39.1,21.5),(38,24),(36.5,26),(35,28),(34.9,29.5),(34.2,27.8),(33.2,28.5),(32.6,29.9)]
IB=[(-9.4,40),(-9,38.7),(-8.9,37),(-6.3,36.8),(-5.6,36),(-2,36.8),(0,38.8),(-0.3,39.5),(0.5,40)]
GR=[(20.6,40),(21,38.5),(22.5,36.4),(23.2,38),(24,38.2),(22.8,40)]
LANDS=[AF,MG,ME,IB,GR]

def inside(x,y,P):
    c=False;n=len(P)
    for i in range(n):
        x1,y1=P[i];x2,y2=P[(i+1)%n]
        if (y1>y)!=(y2>y) and x<(x2-x1)*(y-y1)/(y2-y1)+x1: c=not c
    return c
g=lambda x,y,cx,cy,s:math.exp(-((x-cx)**2+(y-cy)**2)/(2*s*s))
def cropmask(x,y):
    if not inside(x,y,AF) or y>17: return False
    if 8<=y<=15.5 and -17<=x<=39: return True
    if 33<=x<=42 and 4<=y<=14.5: return True
    if 4<=y<8 and -11<=x<=10: return True
    if 29<=x<=38 and -11<=y<=3: return True
    if 25<=x<=35.5 and -30<=y<=-12: return True
    if 13<=x<=25 and -17<=y<=-8: return (int(x*3+y*7)%3)!=0
    return False
def country(x,y):
    B=[("Ethiopia",35,43,4,14.8),("Senegal",-17.5,-11.5,12,16.6),("Mali",-11.5,-4,11,16),("Burkina Faso",-4,2,9.5,15),
       ("Niger",0,14,13.2,16),("Nigeria",3,13.5,4,13.2),("Chad",13.5,24,8,16),("Sudan",22,35,9.8,16),("Sudan",35,39,14.8,16),
       ("South Sudan",24,35,3.5,9.8),("Guinea",-15,-8,7,12),("Côte d'Ivoire",-8.5,-3,4,11),("Ghana",-3,1,4,11.2),("Benin",1,3,4,12.5),
       ("Cameroon",8.5,16,2,8),("Kenya",34,42,-4.5,4),("Uganda",29,34,-1.5,4),("Tanzania",29,40,-11.6,-1.5),("Angola",11,22,-18,-5),
       ("Malawi",33,35.6,-17,-9.4),("Zambia",22,33,-18,-8),("Mozambique",32,41,-27,-10.5),("Zimbabwe",25.5,33,-22.4,-15.5),
       ("Botswana",19,26,-27,-17.8),("South Africa",16,33,-35,-22.4)]
    for n,a,b,c,d in B:
        if a<=x<b and c<=y<d: return n
    return "Liberia" if x<-8 else "Togo"
def zone(x,y):
    if y>=11 or (y>=9.8 and x<34): return "sahel"
    if 35<=x<=43 and y>=4: return "ethiopia"
    if y>=4 and x<16: return "guinea"
    if y>=-4.5: return "eastafrica"
    return "south"
def aridity(x,y,z):
    if z=="sahel": return "arid" if y>=13.3 else "semi-arid"
    if z=="ethiopia": return "humid" if (x<38.5 and y<9.5) else ("dry sub-humid" if y<12 else "semi-arid")
    if z=="guinea": return "humid" if y<7 else "dry sub-humid"
    if z=="eastafrica": return "humid" if x<36.5 else "semi-arid"
    return "semi-arid" if (y<-22 or x<24) else "dry sub-humid"
CROPS={"sahel":["sorghum","millet"],"ethiopia":["teff","maize","sorghum"],"guinea":["maize","cassava"],"eastafrica":["maize","bean"],"south":["maize"]}
CAL={"sahel":"GGGHH...","ethiopia":"PGGGHH..","guinea":".PGGH...","eastafrica":"...PGGHH","south":"....PPGG"}
PK={"sahel":(2.0,1.4),"ethiopia":(2.6,1.6),"guinea":(3.0,2.2),"eastafrica":(5.2,1.6),"south":(7.4,1.8)}
h=lambda x,y,k:(math.sin(x*12.9898+y*78.233+k*3.1)*43758.5453)%1
def truth(x,y,L):  # Oct, Nov, Dec
    return (-1.6*g(x,y,32,12.5,5)*(1-0.2*L) +(0.4+0.45*L)*g(x,y,38,0,4.5) -(0.2+0.4*L)*g(x,y,29,-18,6)
            +0.6*g(x,y,-3,13,6)*(1-0.4*L) +0.3*math.sin(0.8*x+1.3*L)*math.cos(0.6*y))

CROP_SHIFT = 1   # sample issue 1 Sep 2026: months Jun 2026 - Jan 2027 (the mockup patterns start in Jul)
cells = []
n = int(round(1 / RES))
for X in range(-18 * n, 52 * n):
    for Y in range(-35 * n, 20 * n):
        x, y = (X + 0.5) * RES, (Y + 0.5) * RES
        if not cropmask(x, y): continue
        z = zone(x, y); ai = aridity(x, y, z)
        pk, wd = PK[z]; pk += CROP_SHIFT
        wet = ai in ("humid", "dry sub-humid"); base = (0.30 if wet else 0.15) + (0.12 if ai == "humid" else 0); amp = 0.30 if wet else 0.24
        mu = [base + amp * math.exp(-((i - pk) ** 2) / (2 * wd * wd)) for i in range(8)]
        sd = [0.02 + 0.09 * amp * math.exp(-((i - pk) ** 2) / (2 * (wd + 0.6) ** 2)) for i in range(8)]
        o = [-1.4 * g(x, y, 32, 12.5, 5) * f + 0.7 * g(x, y, -3, 13, 6) + 0.4 * math.sin(1.1 * x - 0.7 * y + f) for f in (0.7, 0.9, 1.0)]
        tr = [truth(x, y, L) for L in range(3)]
        def m(k, w, a): return [round(w * tr[L] + a * (h(x, y, k + L) - 0.5), 2) for L in range(3)]
        rf_all = h(x, y, 99) > 0.013
        smap_ok = rf_all and not (ai == "humid" and h(x, y, 7) < 0.85) and h(x, y, 11) > 0.06
        f = {"pers": [round(o[2], 2)] * 3, "clim": [0, 0, 0]}
        if rf_all:
            f["ndvi"] = [round(o[2] * 0.7 ** (L + 1) + 0.25 * tr[L], 2) for L in range(3)]
            f["fsm"] = m(1, 0.8, 0.9); f["fsc"] = m(2, 0.85, 0.8)
        if smap_ok: f["smap"] = m(3, 0.9, 0.75)
        cal = "." + CAL[z][:-1]
        cells.append(dict(lon=x, lat=y, c=country(x, y), ai=ai, cr=", ".join(CROPS[z]),
                          mu=[round(v, 3) for v in mu], sd=[round(v, 3) for v in sd],
                          p05=[round(a - 1.645 * b, 3) for a, b in zip(mu, sd)], p95=[round(a + 1.645 * b, 3) for a, b in zip(mu, sd)],
                          o=[round(v, 2) for v in o], f=f, cal={c: cal for c in CROPS[z]}))
ox, oy = [], []
for P in LANDS:
    for a, b in P + [P[0]]: ox.append(a); oy.append(b)
    ox.append(None); oy.append(None)
months = ["2026-06", "2026-07", "2026-08", "2026-09", "2026-10", "2026-11", "2026-12", "2027-01"]
models = [dict(id="smap", label="SMAP–FLDAS*", desc="NDVI + SMAP SM + FLDAS P, T IC + FLDAS SM Forecast"),
          dict(id="fsc", label="FLDAS SM + climate", desc="NDVI + FLDAS SM IC + FLDAS P, T IC + FLDAS SM Forecast"),
          dict(id="fsm", label="FLDAS SM", desc="NDVI + FLDAS SM IC + FLDAS SM Forecast"),
          dict(id="ndvi", label="NDVI ONLY", desc="Past NDVI only"),
          dict(id="pers", label="Persistence", desc="The August anomaly kept for the next three months"),
          dict(id="clim", label="Climatology", desc="Normal NDVI for the month (2003–2025 average)")]
for mm in models: mm["n"] = f"{sum(1 for c in cells if mm['id'] in c['f']):,}"
os.makedirs(os.path.dirname(OUT) or ".", exist_ok=True)
json.dump(dict(sample=True, issue="2026-09-01", ic_month="2026-08", months=months, obs_months=months[:3], lead_months=months[3:6],
               models=models, cells=cells, outline=dict(x=ox, y=oy)), open(OUT, "w"), ensure_ascii=False)
print(len(cells), "synthetic grid cells ->", OUT)
