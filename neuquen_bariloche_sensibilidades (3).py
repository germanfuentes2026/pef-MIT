"""
NEUQUÉN – BARILOCHE – Panel de Sensibilidades Financieras
==========================================================
Replicación fiel del modelo NEUQUEN_BARILOCHE.xlsx (GESTIÓN – MIT).

CONVENCIÓN DE ÍNDICES (igual que el xlsx):
  Año 1  = 2026  → índice [0]  – Puesta en valor + Crédito LP, sin peaje
  Año 2  = 2027  → índice [1]  – Primer año con ingresos de peaje
  ...
  Año 10 = 2035  → índice [9]  – Último año con ingresos de peaje
  El VAN/MIRR/TIR se calculan sobre los 10 flujos [0..9].

Instalación:
    pip install streamlit pandas plotly numpy

Ejecución:
    streamlit run neuquen_bariloche_sensibilidades.py
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
    0,                        # Año 1 (2026) – puesta en valor, sin cobro
    24_019_743_351.507931,    # Año 2 (2027)
    24_740_335_652.053169,    # Año 3 (2028)
    25_482_545_721.614765,    # Año 4 (2029)
    26_247_022_093.263210,    # Año 5 (2030)
    27_034_432_756.061108,    # Año 6 (2031)
    27_845_465_738.742943,    # Año 7 (2032)
    28_680_829_710.905231,    # Año 8 (2033)
    29_541_254_602.232388,    # Año 9 (2034)
    30_427_492_240.299358,    # Año 10 (2035)
], dtype=float)

# ── Crédito LP (solo Año 1) ────────────────────────────────────
CREDITO_LP = np.zeros(N)
CREDITO_LP[0] = 5_490_896_250.0

# ── OPEX – Conservación y Mantenimiento con IVA ───────────────
# Constante todos los años: $6.536.781.250
OPEX_BASE = np.full(N, 6_536_781_250.0)

# ── Amortización deuda (hoja FLUJO) ───────────────────────────
# Año de gracia en Año 1; cuotas Año 2–7 (índices 1–6)
# Cuota Año 2 incluye gastos administrativos
AMORT_DEUDA_BASE = np.array([
    0,                       # Año 1
    1_260_748_676.455678,    # Año 2 (cuota + gastos admin)
    1_205_839_713.955678,    # Año 3
    1_205_839_713.955678,    # Año 4
    1_205_839_713.955678,    # Año 5
    1_205_839_713.955678,    # Año 6
    1_205_839_713.955678,    # Año 7
    0,                       # Año 8
    0,                       # Año 9
    0,                       # Año 10
], dtype=float)

# ── Garantías anuales (póliza de seguro de caución) ───────────
GARANTIAS = np.full(N, 14_000_000.0)

# ── Impuestos tomados directamente de hoja FLUJO (Proyecto Centro) ──

# IVA a pagar (saldo neto: débito – crédito, pagado cuando positivo)
IMP_IVA_BASE = np.array([
    0,                       # Año 1  (crédito > débito → no hay pago)
    865_127_024.158216,      # Año 2
    2_175_874_191.745283,    # Año 3
    1_194_870_874.347480,    # Año 4
    1_354_311_267.953561,    # Año 5
    1_520_006_820.559514,    # Año 6
    1_692_270_302.446630,    # Año 7
    2_988_128_570.918875,    # Año 8
    4_271_941_207.016976,    # Año 9
    4_425_751_045.028599,    # Año 10
], dtype=float)

IMP_GANANCIAS_BASE = np.array([
    0,
    1_764_587_797.871494,    # Año 2
    3_974_402_124.068939,    # Año 3
    3_447_068_902.403382,    # Año 4
    2_927_917_509.365389,    # Año 5
    2_468_129_759.172087,    # Año 6
    1_777_352_732.401003,    # Año 7
    1_789_185_465.492349,    # Año 8
    2_783_310_214.507095,    # Año 9
    3_784_569_052.066667,    # Año 10
], dtype=float)

IMP_IB_BASE = np.array([
    0,
    496_275_689.080742,      # Año 2
    511_163_959.753165,      # Año 3
    526_498_878.545760,      # Año 4
    542_293_844.902132,      # Año 5
    558_562_660.249196,      # Año 6
    575_319_540.056672,      # Año 7
    592_579_126.258373,      # Año 8
    610_356_500.046124,      # Año 9
    628_667_195.047507,      # Año 10
], dtype=float)

IMP_MUNICIPAL_BASE = np.array([
    0,
    99_255_137.816148,       # Año 2
    102_232_791.950633,      # Año 3
    105_299_775.709152,      # Año 4
    108_458_768.980426,      # Año 5
    111_712_532.049839,      # Año 6
    115_063_908.011334,      # Año 7
    118_515_825.251675,      # Año 8
    122_071_300.009225,      # Año 9
    125_733_439.009501,      # Año 10
], dtype=float)

# Sellos: primeros 5 años (Año 1–5 = índices 0–4)
IMP_SELLOS_BASE = np.array([
    145_213_785.123967,      # Año 1
    145_213_785.123967,      # Año 2
    145_213_785.123967,      # Año 3
    145_213_785.123967,      # Año 4
    145_213_785.123967,      # Año 5
    0, 0, 0, 0, 0,
], dtype=float)

# DB/CR: todos los años
IMP_DBCR_BASE = np.array([
    65_890_755.000000,       # Año 1
    288_236_920.218095,      # Año 2
    296_884_027.824638,      # Año 3
    305_790_548.659377,      # Año 4
    314_964_265.119159,      # Año 5
    324_413_193.072733,      # Año 6
    334_145_588.864915,      # Año 7
    344_169_956.530863,      # Año 8
    354_495_055.226789,      # Año 9
    365_129_906.883592,      # Año 10
], dtype=float)

# ── CAPEX con IVA (hoja CAPEX) ─────────────────────────────────
# Puesta en Valor: Año 1 (índice 0)
# Repavimentación: Años 3–8 (índices 2–7)
PUESTA_VALOR = np.zeros(N)
PUESTA_VALOR[0] = 7_844_137_500.0

REPAV = np.array([
    0,                       # Año 1
    0,                       # Año 2
    6_536_781_250.0,         # Año 3
    13_073_562_500.0,        # Año 4
    13_073_562_500.0,        # Año 5
    13_073_562_500.0,        # Año 6
    13_073_562_500.0,        # Año 7
    6_536_781_250.0,         # Año 8
    0,                       # Año 9
    0,                       # Año 10
], dtype=float)

CAPEX_BASE = PUESTA_VALOR + REPAV

# ── Parámetros de Ganancias (hoja IMPUESTOS) ──────────────────
# GASTOS en base imponible (sin IVA): OPEX/1.15 + Garantías + otros fijos
# Del xlsx: GASTOS = 5.902.992.117,12 constante en todos los años
GASTOS_IIGG_BASE = 5_902_992_117.117115   # constante

# AMORTIZACIÓN impositiva (variante 2: 10 años obras, 5 años repav)
# Extraída directamente de IMPUESTOS → "AMORTIZACION ANNUAL TOTAL" variante 2
AMORT_IMP_BASE = np.array([
    648_275_826.446281,      # Año 1
    648_275_826.446281,      # Año 2
    1_728_735_537.190082,    # Año 3
    3_889_654_958.677685,    # Año 4
    6_050_574_380.165288,    # Año 5
    8_211_493_801.652890,    # Año 6
    10_912_643_078.512394,   # Año 7
    11_632_949_552.341595,   # Año 8
    9_472_030_130.853993,    # Año 9
    7_311_110_709.366388,    # Año 10
], dtype=float)

# Intereses deducibles del préstamo (30% del interés total, Año 2–7)
# Extraídos de hoja IMPUESTOS → "Calculo Intereses Deducibles Prestamo II"
INT_DEDUCIBLES_BASE = np.array([
    0,
    466_726_181.250000,      # Año 2
    403_901_530.970017,      # Año 3
    335_736_785.416236,      # Año 4
    261_778_036.490384,      # Año 5
    181_532_793.905834,      # Año 6
    94_466_705.701597,       # Año 7
    0, 0, 0,
], dtype=float)

# INGRESOS para base imponible de Ganancias (sin IVA = peaje / 1.21)
# Del xlsx: INGRESOS en hoja IMPUESTOS (sin IVA)
INGRESOS_IIGG_BASE = np.array([
    0,
    19_851_027_563.229694,   # Año 2
    20_446_558_390.126587,   # Año 3
    21_059_955_141.830383,   # Año 4
    21_691_753_796.085297,   # Año 5
    22_342_506_409.967857,   # Año 6
    23_012_781_602.266895,   # Año 7
    23_703_165_050.334904,   # Año 8
    24_414_260_001.844948,   # Año 9
    25_146_687_801.900295,   # Año 10
], dtype=float)

# ── Alícuotas base ─────────────────────────────────────────────
AL_IVA_BASE       = 0.21
AL_GANANCIAS_BASE = 0.35
AL_IB_BASE        = 0.025
AL_MUNICIPAL_BASE = 0.005
AL_SELLOS_BASE    = 0.012
AL_DBCR_BASE      = 0.012

# Tráfico
TARIFA_BASE              = 6_000.0   # ARS/UTEQ sin IVA
UTEQ_ANO2               = PEAJE_BASE[1] / (TARIFA_BASE * (1 + AL_IVA_BASE))  # UTEQs Año 2
TRAFICO_CREC_BASE        = 0.03

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
    # Año 2: UTEQ_ANO2 (arranque, solo escala por tarifa)
    # Año 3+: crece (3% + delta) sobre el año anterior
    tasa_eff = max(TRAFICO_CREC_BASE + delta_trafico, -0.50)
    uteq = np.zeros(N)
    uteq[0] = 0.0
    uteq[1] = UTEQ_ANO2   # arranque fijo (el Año 1 crece 5% vs 2023, ya está en datos base)
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
    # BASE_antes = Ingresos – Gastos_constante – Impuestos_deducibles (IB+Mun+Sellos+DBCR)
    # BASE = BASE_antes – Amortización – Intereses deducibles
    # (igual que xlsx hoja IMPUESTOS)
    ingresos_iigg = INGRESOS_IIGG_BASE * factor
    imp_ded = imp_ib + imp_municipal + imp_sellos + imp_dbcr   # impuestos deducibles de Ganancias
    base_imponible = ingresos_iigg - GASTOS_IIGG_BASE - imp_ded - AMORT_IMP_BASE - INT_DEDUCIBLES_BASE

    # Quebrantos acumulados (año 1 tiene quebranto por el año de gracia)
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

    # ── Métricas sobre 10 períodos ──────────────────────────────
    van     = _npv(tasa_van, flujo)
    van_egr = _npv(tasa_van, total_egresos)
    van_ing = _npv(tasa_van, total_ingresos)
    vaff_vae = van / van_egr if van_egr != 0 else float("nan")
    mirr_val = _mirr(flujo, tasa_van)

    # Payback: año de concesión en que flujo acumulado ≥ inversión total en obras
    inv_obras = float(np.sum(PUESTA_VALOR))  # Payback sobre puesta en valor (igual que xlsx)
    payback   = next((y + 1 for y, v in enumerate(acum) if v >= inv_obras), None)

    return dict(
        flujo         = flujo,
        total_ing     = total_ingresos,
        total_egr     = total_egresos,
        peaje         = peaje,
        capex         = capex,
        opex          = opex,
        amort_deuda   = AMORT_DEUDA_BASE.copy(),
        imp_iva       = imp_iva,
        imp_ganancias = imp_ganancias,
        imp_ib        = imp_ib,
        imp_municipal = imp_municipal,
        imp_sellos    = imp_sellos,
        imp_dbcr      = imp_dbcr,
        total_imp     = total_impuestos,
        acum          = acum,
        van           = van,
        van_ing       = van_ing,
        van_egr       = van_egr,
        vaff_vae      = vaff_vae,
        mirr          = mirr_val,
        payback       = payback,
        inv_obras     = inv_obras,
        uteq          = uteq,
    )


# ══════════════════════════════════════════════════════════════
# 3.  CONSTANTES BASE
# ══════════════════════════════════════════════════════════════

_base = run_model()
MIRR_BASE     = _base["mirr"]
VAN_BASE      = _base["van"]
VAFF_VAE_BASE = _base["vaff_vae"]

YEARS_LABEL = [f"Año {y+1}\n({2025+y+1})" for y in range(N)]
YEARS_INT   = list(range(2026, 2036))   # 2026..2035


# ══════════════════════════════════════════════════════════════
# 4.  APP STREAMLIT
# ══════════════════════════════════════════════════════════════

st.set_page_config(
    page_title="Neuquén–Bariloche – Sensibilidades",
    page_icon="🏔️",
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
    st.markdown("## 🏔️ NEUQUÉN – BARILOCHE")
    st.markdown("**GESTIÓN – MIT · 2026–2035**")
    st.markdown("---")

    st.markdown('<div class="sh">🚗 Tránsito y Tarifa</div>', unsafe_allow_html=True)
    tarifa_input = st.number_input(
        "Tarifa base (ARS/UTEQ sin IVA)",
        min_value=1_000, max_value=50_000,
        value=int(TARIFA_BASE), step=10,
        help=f"Base xlsx: $ {TARIFA_BASE:,.0f}. Cobro desde Año 2 (2027)."
    )
    st.caption(
        "📌 **Año 1 (2026):** sin peaje — puesta en valor + crédito LP.  \n"
        "**Año 2 (2027):** arranque tránsito (+5% vs 2023 base).  \n"
        "**Año 3–10:** crece a tasa base 3% + Δ abajo."
    )
    delta_trafico_pp = st.slider(
        "Δ tasa crecimiento anual Año 3–10 (±pp sobre base 3%)",
        min_value=-3.0, max_value=5.0, value=0.0, step=0.01,
        format="%.2f pp",
    )
    delta_trafico = delta_trafico_pp / 100

    st.markdown('<div class="sh">🏗️ CAPEX – Repavimentación</div>', unsafe_allow_html=True)
    st.caption("Sin obras obligatorias. Repavim. en Años 3–8.")
    delta_repav = st.slider(
        "Repavimentación (%)",
        min_value=-40, max_value=100, value=0, step=1,
    ) / 100

    st.markdown('<div class="sh">⚙️ OPEX – Conservación y Mantenimiento</div>', unsafe_allow_html=True)
    delta_opex = st.slider(
        "Variación OPEX (%)",
        min_value=-40, max_value=100, value=0, step=1
    ) / 100

    st.markdown('<div class="sh">💰 Alícuotas impositivas</div>', unsafe_allow_html=True)
    al_ganancias = st.slider("Ganancias (%)", 0.0, 55.0, 35.0, 0.1,
                              format="%.1f %%", help="Base: 35%") / 100
    al_ib        = st.slider("Ingresos Brutos (%)", 0.0, 10.0, 2.5, 0.1,
                              format="%.1f %%", help="Base: 2.5%") / 100
    al_municipal = st.slider("Tasas Municipales (%)", 0.0, 3.0, 0.5, 0.1,
                              format="%.1f %%", help="Base: 0.5%") / 100
    al_sellos    = st.slider("Impuesto de Sellos (%)", 0.0, 5.0, 1.2, 0.1,
                              format="%.1f %%", help="Base: 1.2% (Años 1–5)") / 100
    al_dbcr      = st.slider("Débitos y Créditos Bancarios (%)", 0.0, 5.0, 1.2, 0.1,
                              format="%.1f %%", help="Base: 1.2%") / 100
    al_iva_peaje = st.slider("IVA sobre peaje (%)", 0, 27, 21, 1,
                              help="Base: 21%") / 100

    st.markdown('<div class="sh">📐 Tasa de descuento VAN</div>', unsafe_allow_html=True)
    tasa_van = st.slider("Tasa de descuento (%)", 5.0, 25.0, 10.0, 0.1,
                          format="%.1f %%") / 100

    st.markdown("---")
    if st.button("↺  Resetear todo al base", use_container_width=True):
        st.rerun()

# ── EJECUTAR MODELO ───────────────────────────────────────────
sc = run_model(
    delta_capex_repav = delta_repav,
    delta_opex        = delta_opex,
    delta_trafico     = delta_trafico,
    tarifa            = float(tarifa_input),
    al_ganancias      = al_ganancias,
    al_ib             = al_ib,
    al_municipal      = al_municipal,
    al_sellos         = al_sellos,
    al_dbcr           = al_dbcr,
    al_iva_peaje      = al_iva_peaje,
    tasa_van          = tasa_van,
)


# ── HELPERS ───────────────────────────────────────────────────
def fmt_ars(v):
    if abs(v) >= 1e12: return f"$ {v/1e12:.2f} B"
    if abs(v) >= 1e9:  return f"$ {v/1e9:.2f} MM"
    return f"$ {v:,.0f}"

def delta_html(new, base, flip=False):
    if base == 0 or (isinstance(new, float) and np.isnan(new)):
        return '<span class="neu">—</span>'
    d = (new - base) / abs(base)
    good = (d >= 0) if not flip else (d <= 0)
    cls = "pos" if good else "neg"
    sgn = "+" if d > 0 else ""
    return f'<span class="{cls}">{sgn}{d:.1%} vs base</span>'

def kpi(label, value_str, new, base, flip=False):
    return f"""<div class="kpi">
  <div class="lbl">{label}</div>
  <div class="val">{value_str}</div>
  <div class="dlt">{delta_html(new, base, flip)}</div>
</div>"""

PL = dict(
    plot_bgcolor="#181e2d", paper_bgcolor="#181e2d",
    font=dict(color="#c5cdd8", size=12),
    xaxis=dict(gridcolor="#252f45", zeroline=False),
    yaxis=dict(gridcolor="#252f45", zeroline=False),
)
C = dict(pos="#3ecf8e", neg="#f76e6e", acc="#6c7fe8",
         warn="#f0a742", pur="#a855f7", gry="#64748b")


# ══════════════════════════════════════════════════════════════
# 5.  ENCABEZADO Y KPIs
# ══════════════════════════════════════════════════════════════
st.markdown("# 🏔️ NEUQUÉN – BARILOCHE — Análisis de Sensibilidades")
st.markdown(
    "Concesión vial 10 años · 2026–2035 &nbsp;|&nbsp; 360.65 km &nbsp;|&nbsp; "
    "Modificá los parámetros ← para ver el impacto en tiempo real"
)
st.divider()

c1, c2, c3, c4 = st.columns(4)
mirr_s = f"{sc['mirr']:.2%}"    if not np.isnan(sc["mirr"])     else "n/d"
vaff_s = f"{sc['vaff_vae']:.2%}" if not np.isnan(sc["vaff_vae"]) else "n/d"
pb     = sc["payback"]
pb_s   = f"Año {pb}  ({2025 + pb})" if pb is not None else "No recupera"

c1.markdown(kpi("VAFF / VAE", vaff_s, sc["vaff_vae"], VAFF_VAE_BASE), unsafe_allow_html=True)
c2.markdown(kpi(f"VAN  (tasa {tasa_van:.0%})", fmt_ars(sc["van"]), sc["van"], VAN_BASE), unsafe_allow_html=True)
c3.markdown(kpi("TIR Modificada (MIRR)", mirr_s, sc["mirr"], MIRR_BASE), unsafe_allow_html=True)
c4.markdown(kpi(f"Payback obras · {fmt_ars(sc['inv_obras'])}", pb_s, 0, 0), unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════
# 6.  TABS
# ══════════════════════════════════════════════════════════════
tab1, tab2, tab3 = st.tabs([
    "📊 Flujo de Fondos",
    "🌪️ Tornado & Spider",
    "🔥 Mapas de calor",
])

# ─────────────────────────────────────────────────────────────
# TAB 1 – FLUJO DE FONDOS
# ─────────────────────────────────────────────────────────────
with tab1:
    fig = make_subplots(
        rows=2, cols=2,
        subplot_titles=[
            "Flujo Neto Anual  ($ MM ARS)",
            "Flujo Acumulado  ($ MM ARS)",
            "Composición de Egresos  ($ MM ARS)",
            "Ingresos vs Egresos  ($ MM ARS)",
        ],
        vertical_spacing=0.16, horizontal_spacing=0.10,
    )

    bc = [C["pos"] if v >= 0 else C["neg"] for v in sc["flujo"]]
    fig.add_trace(go.Bar(x=YEARS_INT, y=sc["flujo"]/1e9,
                         marker_color=bc, name="Flujo Neto"), row=1, col=1)
    fig.add_hline(y=0, line_dash="dot", line_color="#888", row=1, col=1)

    fig.add_trace(go.Scatter(
        x=YEARS_INT, y=sc["acum"]/1e9, mode="lines+markers",
        line=dict(color=C["acc"], width=2.5), marker=dict(size=5),
        fill="tozeroy", fillcolor="rgba(108,127,232,.12)", name="Acumulado"),
        row=1, col=2)
    fig.add_hline(y=0, line_dash="dot", line_color="#888", row=1, col=2)

    fig.add_trace(go.Bar(x=YEARS_INT, y=sc["capex"]/1e9,
                         name="CAPEX", marker_color=C["neg"]), row=2, col=1)
    fig.add_trace(go.Bar(x=YEARS_INT, y=sc["opex"]/1e9,
                         name="OPEX", marker_color=C["warn"]), row=2, col=1)
    fig.add_trace(go.Bar(x=YEARS_INT, y=sc["total_imp"]/1e9,
                         name="Impuestos", marker_color=C["pur"]), row=2, col=1)
    fig.add_trace(go.Bar(x=YEARS_INT, y=sc["amort_deuda"]/1e9,
                         name="Deuda LP", marker_color=C["gry"]), row=2, col=1)

    fig.add_trace(go.Scatter(x=YEARS_INT, y=sc["total_ing"]/1e9,
                              mode="lines", line=dict(color=C["pos"], width=2.5),
                              name="Ingresos"), row=2, col=2)
    fig.add_trace(go.Scatter(x=YEARS_INT, y=sc["total_egr"]/1e9,
                              mode="lines", line=dict(color=C["neg"], width=2.5),
                              name="Egresos"), row=2, col=2)

    fig.update_layout(**PL, barmode="stack", height=640, showlegend=True,
                      legend=dict(orientation="h", y=-0.07, bgcolor="rgba(0,0,0,0)"))
    for ax in ["xaxis","xaxis2","xaxis3","xaxis4",
               "yaxis","yaxis2","yaxis3","yaxis4"]:
        fig.update_layout(**{ax: dict(gridcolor="#252f45", zeroline=False)})
    st.plotly_chart(fig, use_container_width=True)

    # Tabla de flujo
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
    fig4.update_layout(**PL, height=370, margin=dict(t=30,b=60,l=100,r=20))
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
    fig5.update_layout(**PL, height=370, margin=dict(t=30,b=60,l=100,r=20))
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
    fig6.update_layout(**PL, height=370, margin=dict(t=30,b=60,l=80,r=20))
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
    fig7.update_layout(**PL, height=370, margin=dict(t=30,b=60,l=100,r=20))
    fig7.update_xaxes(title_text="Alícuota Ganancias")
    fig7.update_yaxes(title_text="Δ crecimiento tránsito")
    st.plotly_chart(fig7, use_container_width=True)


# ── FOOTER ────────────────────────────────────────────────────
st.divider()
st.caption(
    "NEUQUÉN–BARILOCHE (GESTIÓN–MIT) · Flujos base tomados del xlsx al 1° de marzo 2025 · "
    "Concesión 10 años (2026–2035) · 360.65 km · "
    "Variante amortización: 10 años obras, 5 años repavimentaciones."
)
