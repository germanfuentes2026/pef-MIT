"""
PEF_1 – Panel de Sensibilidades Financieras
============================================
Replicación fiel del modelo PEF_1.xlsx (GESTIÓN – MIT).

CONVENCIÓN DE ÍNDICES:
  Año 1  = 2026  → índice [0]  – Puesta en valor + Crédito LP, sin peaje
  Año 2  = 2027  → índice [1]  – Primer año con ingresos de peaje
  ...
  Año 10 = 2035  → índice [9]  – Último año con ingresos de peaje

Instalación:
    pip install streamlit pandas plotly numpy

Ejecución:
    streamlit run pef1_sensibilidades.py
"""

import streamlit as st
import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# ══════════════════════════════════════════════════════════════
# 0.  FUNCIONES FINANCIERAS PURAS
# ══════════════════════════════════════════════════════════════

def _npv(rate: float, cf: np.ndarray) -> float:
    """VAN convención Excel: flujos descontados desde t=1."""
    t = np.arange(1, len(cf) + 1, dtype=float)
    return float(np.sum(cf / (1.0 + rate) ** t))

TASA_FINANCIAMIENTO = 0.085   # finance_rate para MIRR = TNA del préstamo

def _mirr(cf: np.ndarray, reinvest_rate: float) -> float:
    n = len(cf)
    neg = np.where(cf < 0, cf, 0.0)
    pos = np.where(cf > 0, cf, 0.0)
    pv_neg = sum(neg[t] / (1 + TASA_FINANCIAMIENTO) ** t for t in range(n))
    fv_pos = sum(pos[t] * (1 + reinvest_rate) ** (n - 1 - t) for t in range(n))
    if pv_neg >= 0 or fv_pos <= 0:
        return float("nan")
    return (fv_pos / (-pv_neg)) ** (1.0 / (n - 1)) - 1.0


# ══════════════════════════════════════════════════════════════
# 1.  DATOS BASE EXTRAÍDOS DIRECTAMENTE DEL XLSX
#     10 elementos, índice 0 = Año 1 (2026) ... índice 9 = Año 10 (2035)
# ══════════════════════════════════════════════════════════════

N = 10   # períodos de concesión

# ── Ingresos de peaje con IVA (hoja FLUJO, fila "Peajes") ─────
# Año 1 (2026): 0 – sin ingresos; Año 2–10: crecientes al 3% desde arranque
PEAJE_BASE = np.array([
    0,                          # Año 1 (2026) – puesta en valor, sin cobro
    16_031_863_691.577500,      # Año 2 (2027)
    16_512_819_602.324825,      # Año 3 (2028)
    17_008_204_190.394571,      # Año 4 (2029)
    17_518_450_316.106407,      # Año 5 (2030)
    18_044_003_825.589600,      # Año 6 (2031)
    18_585_323_940.357290,      # Año 7 (2032)
    19_142_883_658.568010,      # Año 8 (2033)
    19_717_170_168.325050,      # Año 9 (2034)
    20_308_685_273.374800,      # Año 10 (2035)
], dtype=float)

# ── Crédito LP (solo Año 1) ────────────────────────────────────
CREDITO_LP = np.zeros(N)
CREDITO_LP[0] = 3_379_950_000.0

# ── OPEX – Conservación y Mantenimiento con IVA ───────────────
OPEX_BASE = np.full(N, 3_862_800_000.0)

# ── Amortización deuda (hoja FLUJO) ───────────────────────────
# Año de gracia en Año 1; cuotas Año 2–7 (índices 1–6), sistema francés
AMORT_DEUDA_BASE = np.array([
    0,                          # Año 1
    776_060_463.532956,         # Año 2 (cuota + gastos admin)
    742_260_963.532956,         # Año 3
    742_260_963.532956,         # Año 4
    742_260_963.532956,         # Año 5
    742_260_963.532956,         # Año 6
    742_260_963.532956,         # Año 7
    0,                          # Año 8
    0,                          # Año 9
    0,                          # Año 10
], dtype=float)

# ── Garantías anuales ──────────────────────────────────────────
GARANTIAS = np.full(N, 9_000_000.0)

# ── Impuestos tomados directamente de hoja FLUJO ──────────────

IMP_IVA_BASE = np.array([
    0,                          # Año 1
    790_702_449.918623,         # Año 2
    1_583_102_046.237590,       # Año 3
    985_924_430.275558,         # Año 4
    1_090_953_448.781376,       # Año 5
    1_200_039_402.660214,       # Año 6
    1_313_381_015.482775,       # Año 7
    2_118_576_412.895562,       # Año 8
    2_916_582_749.299676,       # Año 9
    3_019_242_395.630625,       # Año 10
], dtype=float)

IMP_GANANCIAS_BASE = np.array([
    0,
    1_531_907_649.574351,       # Año 2
    2_851_888_451.173071,       # Año 3
    2_537_929_963.834693,       # Año 4
    2_229_327_171.374603,       # Año 5
    1_957_594_887.929159,       # Año 6
    1_544_014_717.544252,       # Año 7
    1_563_278_609.364460,       # Año 8
    2_187_556_911.860271,       # Año 9
    2_816_596_827.893765,       # Año 10
], dtype=float)

IMP_IB_BASE = np.array([
    0,
    331_236_853.131767,         # Año 2
    341_173_958.725720,         # Año 3
    351_409_177.487491,         # Año 4
    361_951_452.812116,         # Año 5
    372_809_996.396479,         # Año 6
    383_994_296.288374,         # Año 7
    395_514_125.177025,         # Año 8
    407_379_548.932336,         # Año 9
    419_600_935.400306,         # Año 10
], dtype=float)

IMP_MUNICIPAL_BASE = np.array([
    0,
    66_247_370.626353,          # Año 2
    68_234_791.745144,          # Año 3
    70_281_835.497498,          # Año 4
    72_390_290.562423,          # Año 5
    74_561_999.279296,          # Año 6
    76_798_859.257675,          # Año 7
    79_102_825.035405,          # Año 8
    81_475_909.786467,          # Año 9
    83_920_187.080061,          # Año 10
], dtype=float)

# Sellos: primeros 5 años (Año 1–5 = índices 0–4)
IMP_SELLOS_BASE = np.array([
    89_387_107.438017,          # Año 1
    89_387_107.438017,          # Año 2
    89_387_107.438017,          # Año 3
    89_387_107.438017,          # Año 4
    89_387_107.438017,          # Año 5
    0, 0, 0, 0, 0,
], dtype=float)

# DB/CR: todos los años
IMP_DBCR_BASE = np.array([
    40_559_400.000000,          # Año 1
    192_382_364.298930,         # Año 2
    198_153_835.227898,         # Año 3
    204_098_450.284735,         # Año 4
    210_221_403.793277,         # Año 5
    216_528_045.907075,         # Año 6
    223_023_887.284287,         # Año 7
    229_714_603.902816,         # Año 8
    236_606_042.019901,         # Año 9
    243_704_223.280498,         # Año 10
], dtype=float)

# ── CAPEX con IVA (hoja CAPEX) ─────────────────────────────────
PUESTA_VALOR = np.zeros(N)
PUESTA_VALOR[0] = 4_828_500_000.0

REPAV = np.array([
    0,                          # Año 1
    0,                          # Año 2
    4_023_750_000.0,            # Año 3
    8_047_500_000.0,            # Año 4
    8_047_500_000.0,            # Año 5
    8_047_500_000.0,            # Año 6
    8_047_500_000.0,            # Año 7
    4_023_750_000.0,            # Año 8
    0,                          # Año 9
    0,                          # Año 10
], dtype=float)

CAPEX_BASE = PUESTA_VALOR + REPAV

# ── Parámetros de Ganancias (hoja IMPUESTOS) ──────────────────
# GASTOS = OPEX sin IVA + Garantías (constante)
GASTOS_IIGG_BASE = 3_488_999_999.999999   # constante

# AMORTIZACIÓN impositiva (10 años obras, 5 años repav) – variante 2
AMORT_IMP_BASE = np.array([
    399_049_586.776860,         # Año 1
    399_049_586.776860,         # Año 2
    1_064_132_231.404959,       # Año 3
    2_394_297_520.661157,       # Año 4
    3_724_462_809.917356,       # Año 5
    5_054_628_099.173553,       # Año 6
    6_717_334_710.743801,       # Año 7
    7_160_723_140.495868,       # Año 8
    5_830_557_851.239669,       # Año 9
    4_500_392_561.983471,       # Año 10
], dtype=float)

# Intereses deducibles del préstamo (Art. 85 – 30% del interés total)
INT_DEDUCIBLES_BASE = np.array([
    0,
    287_295_750.000000,         # Año 2
    248_623_706.849699,         # Año 3
    206_664_540.031622,         # Año 4
    161_138_844.034009,         # Año 5
    111_743_463.876598,         # Año 6
    58_149_476.405808,          # Año 7
    0, 0, 0,
], dtype=float)

# INGRESOS para base imponible de Ganancias (sin IVA = peaje / 1.21)
INGRESOS_IIGG_BASE = np.array([
    0,
    13_249_474_125.270660,      # Año 2
    13_646_958_349.028782,      # Año 3
    14_056_367_099.499645,      # Año 4
    14_478_058_112.484634,      # Año 5
    14_912_399_855.859173,      # Año 6
    15_359_771_851.534950,      # Año 7
    15_820_565_007.081000,      # Año 8
    16_295_181_957.293430,      # Año 9
    16_784_037_416.012234,      # Año 10
], dtype=float)

# ── Alícuotas base ─────────────────────────────────────────────
AL_IVA_BASE       = 0.21
AL_GANANCIAS_BASE = 0.35
AL_IB_BASE        = 0.025
AL_MUNICIPAL_BASE = 0.005
AL_SELLOS_BASE    = 0.012
AL_DBCR_BASE      = 0.012

# ── Tráfico ────────────────────────────────────────────────────
TARIFA_BASE        = 6_000.0   # ARS/UTEQ sin IVA
UTEQ_ANO2          = PEAJE_BASE[1] / (TARIFA_BASE * (1 + AL_IVA_BASE))  # UTEQs Año 2
TRAFICO_CREC_BASE  = 0.03

TASA_VAN_BASE = 0.10


# ══════════════════════════════════════════════════════════════
# 2.  MODELO DE SENSIBILIDAD
# ══════════════════════════════════════════════════════════════

def run_model(
    delta_capex_repav = 0.0,
    delta_opex        = 0.0,
    delta_trafico     = 0.0,    # Δpp sobre tasa base 3% (aplicado Año 3+)
    tarifa            = TARIFA_BASE,
    al_ganancias      = AL_GANANCIAS_BASE,
    al_ib             = AL_IB_BASE,
    al_municipal      = AL_MUNICIPAL_BASE,
    al_sellos         = AL_SELLOS_BASE,
    al_dbcr           = AL_DBCR_BASE,
    al_iva_peaje      = AL_IVA_BASE,
    tasa_van          = TASA_VAN_BASE,
):
    # ── Tráfico ─────────────────────────────────────────────────
    # Año 1: sin peaje
    # Año 2: UTEQ_ANO2 (arranque fijo)
    # Año 3+: crece (3% + delta) sobre el año anterior
    tasa_eff = max(TRAFICO_CREC_BASE + delta_trafico, -0.50)
    uteq = np.zeros(N)
    uteq[0] = 0.0
    uteq[1] = UTEQ_ANO2
    for y in range(2, N):
        uteq[y] = uteq[y - 1] * (1 + tasa_eff)

    # ── Ingresos de peaje con IVA ───────────────────────────────
    tarifa_con_iva = tarifa * (1 + al_iva_peaje)
    peaje = np.zeros(N)
    peaje[0] = 0.0
    for y in range(1, N):
        peaje[y] = uteq[y] * tarifa_con_iva

    # Factor para escalar impuestos proporcionales a ingresos
    factor_trafico = np.ones(N)
    for y in range(1, N):
        uteq_base_y = UTEQ_ANO2 * ((1 + TRAFICO_CREC_BASE) ** (y - 1))
        factor_trafico[y] = uteq[y] / uteq_base_y if uteq_base_y > 0 else 1.0
    factor_trafico[0] = 1.0
    factor_tarifa = tarifa / TARIFA_BASE
    factor = factor_trafico * factor_tarifa

    # ── CAPEX ───────────────────────────────────────────────────
    capex = PUESTA_VALOR + REPAV * (1 + delta_capex_repav)

    # ── OPEX ────────────────────────────────────────────────────
    opex = OPEX_BASE * (1 + delta_opex)

    # ── Impuestos escalados ─────────────────────────────────────
    imp_iva       = IMP_IVA_BASE       * factor * ((1 + al_iva_peaje) / (1 + AL_IVA_BASE))
    imp_ib        = IMP_IB_BASE        * factor * (al_ib       / AL_IB_BASE)
    imp_municipal = IMP_MUNICIPAL_BASE * factor * (al_municipal / AL_MUNICIPAL_BASE)
    imp_sellos    = IMP_SELLOS_BASE    * (al_sellos / AL_SELLOS_BASE)
    imp_dbcr      = IMP_DBCR_BASE      * factor * (al_dbcr     / AL_DBCR_BASE)
    # Año 1: DB/CR sobre crédito LP (no escala por tráfico)
    imp_dbcr[0]   = IMP_DBCR_BASE[0]  * (al_dbcr / AL_DBCR_BASE)

    # ── Impuesto a las Ganancias ────────────────────────────────
    # BASE_antes = Ingresos_sin_iva – GASTOS_cte – Impuestos_deducibles (IB+Mun+Sellos+DBCR)
    # BASE = BASE_antes – Amortización – Intereses deducibles
    ingresos_iigg = INGRESOS_IIGG_BASE * factor
    imp_ded       = imp_ib + imp_municipal + imp_sellos + imp_dbcr
    base_imponible = ingresos_iigg - GASTOS_IIGG_BASE - imp_ded - AMORT_IMP_BASE - INT_DEDUCIBLES_BASE

    quebranto_acum = np.zeros(N)
    imp_ganancias  = np.zeros(N)
    for y in range(N):
        base_y = base_imponible[y] + (quebranto_acum[y - 1] if y > 0 else 0.0)
        if base_y <= 0:
            quebranto_acum[y] = base_y
            imp_ganancias[y]  = 0.0
        else:
            quebranto_acum[y] = 0.0
            imp_ganancias[y]  = base_y * al_ganancias

    total_impuestos = (imp_iva + imp_ganancias + imp_ib +
                       imp_municipal + imp_sellos + imp_dbcr)

    # ── Ingresos y egresos totales ──────────────────────────────
    total_ingresos = peaje + CREDITO_LP
    total_egresos  = capex + opex + AMORT_DEUDA_BASE + total_impuestos + GARANTIAS

    # ── Flujo neto ──────────────────────────────────────────────
    flujo = total_ingresos - total_egresos
    acum  = np.cumsum(flujo)

    # ── Métricas ────────────────────────────────────────────────
    van     = _npv(tasa_van, flujo)
    van_egr = _npv(tasa_van, total_egresos)
    van_ing = _npv(tasa_van, total_ingresos)
    vaff_vae = van / van_egr if van_egr != 0 else float("nan")
    mirr_val = _mirr(flujo, tasa_van)

    # Payback sobre puesta en valor (igual que xlsx)
    inv_obras = float(np.sum(PUESTA_VALOR))
    payback   = next((y + 1 for y, v in enumerate(acum) if v >= inv_obras), None)

    return dict(
        flujo=flujo, total_ing=total_ingresos, total_egr=total_egresos,
        peaje=peaje, capex=capex, opex=opex,
        amort_deuda=AMORT_DEUDA_BASE.copy(),
        imp_iva=imp_iva, imp_ganancias=imp_ganancias, imp_ib=imp_ib,
        imp_municipal=imp_municipal, imp_sellos=imp_sellos, imp_dbcr=imp_dbcr,
        total_imp=total_impuestos, acum=acum,
        van=van, van_ing=van_ing, van_egr=van_egr,
        vaff_vae=vaff_vae, mirr=mirr_val,
        payback=payback, inv_obras=inv_obras, uteq=uteq,
    )


# ══════════════════════════════════════════════════════════════
# 3.  CONSTANTES BASE
# ══════════════════════════════════════════════════════════════

_base = run_model()
MIRR_BASE     = _base["mirr"]
VAN_BASE      = _base["van"]
VAFF_VAE_BASE = _base["vaff_vae"]

YEARS_LABEL = [f"Año {y+1}\n({2026+y})" for y in range(N)]
YEARS_INT   = list(range(2026, 2036))


# ══════════════════════════════════════════════════════════════
# 4.  APP STREAMLIT
# ══════════════════════════════════════════════════════════════

st.set_page_config(
    page_title="PEF_1 – Sensibilidades",
    page_icon="🛣️",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
.main { background: #0e1117; }
.block-container { padding-top: 1.2rem; padding-bottom: 1rem; }

.kpi {
  background: linear-gradient(135deg, #1c2230, #222a3c);
  border: 1px solid #2d3650;
  border-radius: 12px;
  padding: 16px 20px;
  text-align: center;
  margin-bottom: 6px;
}
.kpi .lbl  { color: #7a869a; font-size: .72rem; text-transform: uppercase;
             letter-spacing: .09em; margin-bottom: 3px; }
.kpi .val  { color: #dce4f0; font-size: 1.55rem; font-weight: 700; }
.kpi .dlt  { font-size: .76rem; margin-top: 2px; }
.kpi .pos  { color: #3ecf8e; }
.kpi .neg  { color: #f76e6e; }
.kpi .neu  { color: #7a869a; }

.sh {
  color: #6c7fe8; font-size: .76rem; font-weight: 700;
  text-transform: uppercase; letter-spacing: .1em;
  margin: 12px 0 4px;
  padding-bottom: 3px;
  border-bottom: 1px solid #2d3650;
}

div[data-testid="stSidebar"] { background: #131720; }
</style>
""", unsafe_allow_html=True)

# ── SIDEBAR ───────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 🛣️ PEF_1")
    st.markdown("**GESTIÓN – MIT · 2026–2035**")
    st.markdown("---")

    st.markdown('<div class="sh">📦 CAPEX</div>', unsafe_allow_html=True)
    delta_repav = st.slider("Repavimentación (%)", -50, 100, 0, 5,
                            format="%d%%", key="repav") / 100

    st.markdown('<div class="sh">🔧 OPEX</div>', unsafe_allow_html=True)
    delta_opex = st.slider("Conservación y Mantenimiento (%)", -50, 100, 0, 5,
                           format="%d%%", key="opex") / 100

    st.markdown('<div class="sh">🚗 TRÁNSITO</div>', unsafe_allow_html=True)
    delta_trafico = st.slider("Δ crecimiento tránsito (pp sobre 3%)", -3.0, 5.0, 0.0, 0.5,
                               format="%.1fpp", key="trafico")

    st.markdown('<div class="sh">💰 TARIFA</div>', unsafe_allow_html=True)
    tarifa_input = st.number_input("Tarifa inicial sin IVA ($)", value=6_000, step=500, key="tarifa")

    st.markdown('<div class="sh">📊 IMPUESTOS</div>', unsafe_allow_html=True)
    al_ganancias  = st.slider("Ganancias (%)", 0, 60, 35, 1, format="%d%%") / 100
    al_ib         = st.slider("Ing. Brutos (%)", 0.0, 10.0, AL_IB_BASE*100, 0.5,
                               format="%.1f%%", key="ib") / 100
    al_municipal  = st.slider("Municipal (%)", 0.0, 5.0, AL_MUNICIPAL_BASE*100, 0.1,
                               format="%.1f%%", key="mun") / 100
    al_sellos     = st.slider("Sellos (%)", 0.0, 5.0, AL_SELLOS_BASE*100, 0.1,
                               format="%.1f%%", key="sel") / 100
    al_dbcr       = st.slider("Débitos/Créditos (%)", 0.0, 5.0, AL_DBCR_BASE*100, 0.1,
                               format="%.1f%%", key="dbcr") / 100
    al_iva_peaje  = st.slider("IVA peaje (%)", 0.0, 30.0, AL_IVA_BASE*100, 0.5,
                               format="%.1f%%", key="iva") / 100

    st.markdown('<div class="sh">📐 DESCUENTO</div>', unsafe_allow_html=True)
    tasa_van = st.slider("Tasa de descuento VAN (%)", 4, 25, 10, 1,
                          format="%d%%", key="tasa") / 100

    st.markdown("---")
    if st.button("↺ Restablecer todo", use_container_width=True):
        st.rerun()

# ── RUN MODEL ────────────────────────────────────────────────
sc = run_model(
    delta_capex_repav=delta_repav,
    delta_opex=delta_opex,
    delta_trafico=delta_trafico,
    tarifa=float(tarifa_input),
    al_ganancias=al_ganancias,
    al_ib=al_ib,
    al_municipal=al_municipal,
    al_sellos=al_sellos,
    al_dbcr=al_dbcr,
    al_iva_peaje=al_iva_peaje,
    tasa_van=tasa_van,
)

# ── COLORES ───────────────────────────────────────────────────
C = dict(
    acc="#6c7fe8", pos="#3ecf8e", neg="#f76e6e",
    warn="#f9c74f", pur="#b98cf7", neu="#7a869a",
)
PL = dict(
    plot_bgcolor="#0e1117", paper_bgcolor="#0e1117",
    font=dict(color="#c5cdd8", size=12),
    legend=dict(bgcolor="rgba(0,0,0,0)"),
)

# ── HEADER ───────────────────────────────────────────────────
st.title("🛣️ PEF_1 — Panel de Sensibilidades Financieras")
st.caption("Concesión 10 años · 2026–2035 · 222 km · GESTIÓN–MIT")

# ── KPI CARDS ────────────────────────────────────────────────
def _kpi(label, value, base, fmt="{:.2f}", suffix="", delta_fmt="{:+.2f}"):
    delta = value - base
    cls   = "pos" if delta >= 0 else "neg"
    delta_str = delta_fmt.format(delta) + suffix
    return f"""<div class="kpi">
  <div class="lbl">{label}</div>
  <div class="val">{fmt.format(value)}{suffix}</div>
  <div class="dlt"><span class="{cls}">{delta_str} vs base</span></div>
</div>"""

k1, k2, k3, k4 = st.columns(4)
with k1:
    st.markdown(_kpi("VAN", sc["van"]/1e9, VAN_BASE/1e9,
                     fmt="$ {:.1f} MM", suffix=""), unsafe_allow_html=True)
with k2:
    st.markdown(_kpi("VAFF / VAE", sc["vaff_vae"]*100, VAFF_VAE_BASE*100,
                     fmt="{:.2f}", suffix="%"), unsafe_allow_html=True)
with k3:
    mirr_disp = sc["mirr"]*100 if not np.isnan(sc["mirr"]) else 0.0
    st.markdown(_kpi("MIRR", mirr_disp, MIRR_BASE*100,
                     fmt="{:.2f}", suffix="%"), unsafe_allow_html=True)
with k4:
    pb = sc["payback"] or "N/A"
    pb_b = _base["payback"] or "N/A"
    st.markdown(f"""<div class="kpi">
  <div class="lbl">PAYBACK OBRAS</div>
  <div class="val">Año {pb}</div>
  <div class="dlt"><span class="neu">Base: Año {pb_b}</span></div>
</div>""", unsafe_allow_html=True)

st.markdown("---")

# ── TABS ─────────────────────────────────────────────────────
tab1, tab2, tab3 = st.tabs(["📈 Flujo de Fondos", "🌪️ Tornado & Spider", "🔥 Mapas de Calor"])


# ─────────────────────────────────────────────────────────────
# TAB 1 – FLUJO
# ─────────────────────────────────────────────────────────────
with tab1:
    # ── Gráfico de barras apiladas ────────────────────────────
    st.markdown("#### Flujo neto y acumulado por año")

    fig = make_subplots(specs=[[{"secondary_y": True}]])

    # Barras ingresos / egresos
    fig.add_trace(go.Bar(
        x=YEARS_INT, y=sc["total_ing"]/1e9, name="Ingresos",
        marker_color=C["pos"], opacity=0.85,
    ), secondary_y=False)
    fig.add_trace(go.Bar(
        x=YEARS_INT, y=-sc["total_egr"]/1e9, name="Egresos",
        marker_color=C["neg"], opacity=0.85,
    ), secondary_y=False)

    # Línea flujo neto
    fig.add_trace(go.Scatter(
        x=YEARS_INT, y=sc["flujo"]/1e9, name="Flujo neto",
        mode="lines+markers", line=dict(color=C["acc"], width=2.5),
        marker=dict(size=6),
    ), secondary_y=False)

    # Línea acumulado
    fig.add_trace(go.Scatter(
        x=YEARS_INT, y=sc["acum"]/1e9, name="Acumulado",
        mode="lines+markers", line=dict(color=C["warn"], width=2, dash="dot"),
        marker=dict(size=5),
    ), secondary_y=True)

    fig.add_hline(y=0, line_color="#444", line_dash="solid", line_width=1)
    fig.update_layout(**PL, height=420, barmode="relative",
                      margin=dict(t=30, b=50, l=60, r=60),
                      legend=dict(orientation="h", y=1.08))
    fig.update_yaxes(title_text="$ ARS MM", secondary_y=False,
                     gridcolor="#252f45", zeroline=False)
    fig.update_yaxes(title_text="Acumulado $ ARS MM", secondary_y=True,
                     gridcolor="#252f45", zeroline=False)
    fig.update_xaxes(gridcolor="#252f45", zeroline=False)
    st.plotly_chart(fig, use_container_width=True)

    # ── Composición de egresos ────────────────────────────────
    st.markdown("#### Composición de egresos")

    fig_e = go.Figure()
    cats = [
        ("CAPEX",       sc["capex"],       C["neg"]),
        ("OPEX",        sc["opex"],        C["warn"]),
        ("Deuda",       sc["amort_deuda"], C["pur"]),
        ("IVA",         sc["imp_iva"],     "#4ecdc4"),
        ("Ganancias",   sc["imp_ganancias"],C["acc"]),
        ("IB+Mun",      sc["imp_ib"]+sc["imp_municipal"], "#a8e063"),
        ("Sellos",      sc["imp_sellos"],  "#f7b2ad"),
        ("DB/CR",       sc["imp_dbcr"],    "#ffd6a5"),
        ("Garantías",   GARANTIAS,         C["neu"]),
    ]
    for name, vals, col in cats:
        fig_e.add_trace(go.Bar(
            x=YEARS_INT, y=vals/1e9, name=name,
            marker_color=col, opacity=0.88,
        ))
    fig_e.update_layout(**PL, height=380, barmode="stack",
                        margin=dict(t=30, b=50, l=60, r=20),
                        legend=dict(orientation="h", y=1.08))
    fig_e.update_xaxes(gridcolor="#252f45", zeroline=False)
    fig_e.update_yaxes(title_text="$ ARS MM", gridcolor="#252f45", zeroline=False)
    st.plotly_chart(fig_e, use_container_width=True)

    # ── Tabla detalle ─────────────────────────────────────────
    st.markdown("#### Detalle año a año")
    df = pd.DataFrame({
        "Año":          [f"Año {y+1} ({2026+y})" for y in range(N)],
        "Ingresos MM$": (sc["total_ing"]/1e9).round(2),
        "CAPEX MM$":    (sc["capex"]/1e9).round(2),
        "OPEX MM$":     (sc["opex"]/1e9).round(2),
        "Deuda MM$":    (sc["amort_deuda"]/1e9).round(2),
        "Impuestos MM$":(sc["total_imp"]/1e9).round(2),
        "Egresos MM$":  (sc["total_egr"]/1e9).round(2),
        "Flujo MM$":    (sc["flujo"]/1e9).round(2),
        "Acum MM$":     (sc["acum"]/1e9).round(2),
    })
    st.dataframe(df, use_container_width=True, hide_index=True)


# ─────────────────────────────────────────────────────────────
# TAB 2 – TORNADO + SPIDER
# ─────────────────────────────────────────────────────────────
with tab2:
    st.markdown("#### Gráfico Tornado — impacto individual sobre el VAN")
    st.caption("Shock de ±20% a UNA variable, el resto en el valor del panel.")

    BASE_KW = dict(
        delta_capex_repav=delta_repav, delta_opex=delta_opex,
        delta_trafico=delta_trafico, tarifa=float(tarifa_input),
        al_ganancias=al_ganancias, al_ib=al_ib, al_municipal=al_municipal,
        al_sellos=al_sellos, al_dbcr=al_dbcr, al_iva_peaje=al_iva_peaje,
        tasa_van=tasa_van,
    )

    shocks = {
        "Repavim. +20%":       dict(delta_capex_repav=delta_repav+0.20),
        "Repavim. –20%":       dict(delta_capex_repav=delta_repav-0.20),
        "OPEX +20%":           dict(delta_opex=delta_opex+0.20),
        "OPEX –20%":           dict(delta_opex=delta_opex-0.20),
        "Tránsito +1pp":       dict(delta_trafico=delta_trafico+0.01),
        "Tránsito –1pp":       dict(delta_trafico=delta_trafico-0.01),
        "Tarifa +20%":         dict(tarifa=float(tarifa_input)*1.20),
        "Tarifa –20%":         dict(tarifa=float(tarifa_input)*0.80),
        "Ganancias +10pp":     dict(al_ganancias=min(0.60, al_ganancias+0.10)),
        "Ganancias –10pp":     dict(al_ganancias=max(0.00, al_ganancias-0.10)),
        "IB +2pp":             dict(al_ib=al_ib+0.02),
        "IB –2pp":             dict(al_ib=max(0, al_ib-0.02)),
        "IVA peaje +3pp":      dict(al_iva_peaje=al_iva_peaje+0.03),
        "IVA peaje –3pp":      dict(al_iva_peaje=max(0, al_iva_peaje-0.03)),
        "Db/Cr +1pp":          dict(al_dbcr=al_dbcr+0.01),
        "Db/Cr –1pp":          dict(al_dbcr=max(0, al_dbcr-0.01)),
        "Tasa descuento +2pp": dict(tasa_van=tasa_van+0.02),
        "Tasa descuento –2pp": dict(tasa_van=max(0.01, tasa_van-0.02)),
    }

    base_van = sc["van"]
    rows = []
    for label, ov in shocks.items():
        r = run_model(**{**BASE_KW, **ov})
        rows.append({"Variable": label, "ΔVAN": (r["van"] - base_van) / 1e9})
    df_t = pd.DataFrame(rows).sort_values("ΔVAN")

    fig2 = go.Figure(go.Bar(
        x=df_t["ΔVAN"], y=df_t["Variable"], orientation="h",
        marker_color=["#3ecf8e" if v >= 0 else "#f76e6e" for v in df_t["ΔVAN"]],
        text=[f"$ {v:+.1f} MM" for v in df_t["ΔVAN"]],
        textposition="outside",
    ))
    fig2.add_vline(x=0, line_color="#999", line_dash="dot")
    fig2.update_layout(**PL, height=540, margin=dict(l=180, r=130, t=40, b=50))
    fig2.update_xaxes(title_text="Δ VAN ($ ARS MM)")
    st.plotly_chart(fig2, use_container_width=True)

    st.divider()
    st.markdown("#### Spider — MIRR según variación de cada variable (±40%)")

    rang = np.arange(-40, 45, 10)
    variables = {
        "CAPEX Repavim.":  lambda p: dict(delta_capex_repav=delta_repav + p/100),
        "OPEX":            lambda p: dict(delta_opex=delta_opex + p/100),
        "Tránsito (+pp)":  lambda p: dict(delta_trafico=delta_trafico + p/100),
        "Tarifa (+%)":     lambda p: dict(tarifa=float(tarifa_input) * (1 + p/100)),
        "Ganancias (+pp)": lambda p: dict(al_ganancias=max(0, al_ganancias + p/100)),
    }
    cols_sp = [C["warn"], C["pur"], C["pos"], C["acc"], C["neg"]]

    fig3 = go.Figure()
    for (vname, fn), col in zip(variables.items(), cols_sp):
        mirrs = []
        for p in rang:
            r = run_model(**{**BASE_KW, **fn(p)})
            mirrs.append(r["mirr"]*100 if not np.isnan(r["mirr"]) else None)
        fig3.add_trace(go.Scatter(x=list(rang), y=mirrs, name=vname,
                                   mode="lines+markers",
                                   line=dict(color=col, width=2.5),
                                   marker=dict(size=5)))
    fig3.add_hline(y=MIRR_BASE*100, line_dash="dash", line_color="#aaa",
                   annotation_text=f"Base {MIRR_BASE*100:.1f}%",
                   annotation_position="bottom right")
    fig3.update_layout(**PL, height=400, margin=dict(t=40, b=50, l=60, r=20),
                       legend=dict(bgcolor="rgba(0,0,0,0)"))
    fig3.update_xaxes(title_text="Variación (%)")
    fig3.update_yaxes(title_text="MIRR (%)")
    st.plotly_chart(fig3, use_container_width=True)


# ─────────────────────────────────────────────────────────────
# TAB 3 – MAPAS DE CALOR
# ─────────────────────────────────────────────────────────────
with tab3:
    trafico_rng = np.arange(-2.0, 3.5, 0.5)
    repav_rng   = np.arange(-30, 55, 10)
    opex_rng    = np.arange(-30, 55, 10)
    gan_rng     = np.arange(15, 55, 5)
    tasa_rng    = np.arange(6, 20, 2)

    def heat(**ov):
        return run_model(**{**BASE_KW, **ov})

    # Mapa 1: MIRR = Δtráfico × Repavimentación
    st.markdown("#### MIRR (%) — Δ Tránsito (pp) × Repavimentación CAPEX (%)")
    mat1 = np.array([[
        heat(delta_trafico=delta_trafico+tr/100,
             delta_capex_repav=delta_repav+rp/100)["mirr"] * 100
        for rp in repav_rng] for tr in trafico_rng])

    fig4 = go.Figure(go.Heatmap(
        z=mat1.round(1), x=[f"{c:+d}%" for c in repav_rng],
        y=[f"{t:+.1f}pp" for t in trafico_rng],
        colorscale="RdYlGn", texttemplate="%{z:.1f}%",
        colorbar=dict(title="MIRR (%)", tickfont=dict(color="#c5cdd8")),
    ))
    fig4.update_layout(**PL, height=370, margin=dict(t=30, b=60, l=100, r=20))
    fig4.update_xaxes(title_text="Variación Repavimentación CAPEX")
    fig4.update_yaxes(title_text="Δ crecimiento tránsito")
    st.plotly_chart(fig4, use_container_width=True)

    # Mapa 2: VAN = Δtráfico × OPEX
    st.markdown("#### VAN ($ MM) — Δ Tránsito × OPEX (%)")
    mat2 = np.array([[
        heat(delta_trafico=delta_trafico+tr/100,
             delta_opex=delta_opex+op/100)["van"] / 1e9
        for op in opex_rng] for tr in trafico_rng])

    fig5 = go.Figure(go.Heatmap(
        z=mat2.round(0), x=[f"{o:+d}%" for o in opex_rng],
        y=[f"{t:+.1f}pp" for t in trafico_rng],
        colorscale="RdYlGn", texttemplate="%{z:.0f}",
        colorbar=dict(title="VAN (MM$)", tickfont=dict(color="#c5cdd8")),
    ))
    fig5.update_layout(**PL, height=370, margin=dict(t=30, b=60, l=100, r=20))
    fig5.update_xaxes(title_text="Variación OPEX")
    fig5.update_yaxes(title_text="Δ crecimiento tránsito")
    st.plotly_chart(fig5, use_container_width=True)

    # Mapa 3: VAN = tasa × Repavimentación
    st.markdown("#### VAN ($ MM) — Tasa de descuento × Repavimentación CAPEX (%)")
    mat3 = np.array([[
        heat(tasa_van=td/100, delta_capex_repav=delta_repav+rp/100)["van"] / 1e9
        for rp in repav_rng] for td in tasa_rng])

    fig6 = go.Figure(go.Heatmap(
        z=mat3.round(0), x=[f"{c:+d}%" for c in repav_rng],
        y=[f"{t}%" for t in tasa_rng],
        colorscale="RdYlGn", texttemplate="%{z:.0f}",
        colorbar=dict(title="VAN (MM$)", tickfont=dict(color="#c5cdd8")),
    ))
    fig6.update_layout(**PL, height=370, margin=dict(t=30, b=60, l=80, r=20))
    fig6.update_xaxes(title_text="Variación Repavimentación CAPEX")
    fig6.update_yaxes(title_text="Tasa de descuento")
    st.plotly_chart(fig6, use_container_width=True)

    # Mapa 4: VAFF/VAE = Δtráfico × Ganancias
    st.markdown("#### VAFF/VAE — Δ Tránsito × Alícuota Ganancias (%)")
    mat4 = np.array([[
        heat(delta_trafico=delta_trafico+tr/100, al_ganancias=ga/100)["vaff_vae"]
        for ga in gan_rng] for tr in trafico_rng])
    mat4 = np.nan_to_num(mat4, nan=0.0)

    fig7 = go.Figure(go.Heatmap(
        z=mat4.round(4), x=[f"{g}%" for g in gan_rng],
        y=[f"{t:+.1f}pp" for t in trafico_rng],
        colorscale="RdYlGn", texttemplate="%{z:.3f}",
        colorbar=dict(title="VAFF/VAE", tickfont=dict(color="#c5cdd8")),
    ))
    fig7.update_layout(**PL, height=370, margin=dict(t=30, b=60, l=100, r=20))
    fig7.update_xaxes(title_text="Alícuota Ganancias")
    fig7.update_yaxes(title_text="Δ crecimiento tránsito")
    st.plotly_chart(fig7, use_container_width=True)


# ── FOOTER ────────────────────────────────────────────────────
st.divider()
st.caption(
    "PEF_1 (GESTIÓN–MIT) · Flujos base tomados del xlsx al 1° de marzo 2025 · "
    "Concesión 10 años (2026–2035) · 222 km · "
    "Variante amortización: 10 años obras, 5 años repavimentaciones."
)
