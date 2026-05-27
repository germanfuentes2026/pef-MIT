"""
NEUQUÉN – BARILOCHE – Panel de Sensibilidades Financieras
==========================================================
Replicación fiel del modelo NEUQUEN_BARILOCHE.xlsx.

El modelo NO recalcula el préstamo ni usa WACC.
Los flujos base se toman directamente del xlsx y se
escalan con los factores de sensibilidad ingresados.

Proyecto: NEUQUEN-BARILOCHE (GESTIÓN – MIT)
Concesión: 10 años de operación (Años 1–10: 2026–2035)
Longitud total equivalente: 360.65 km
Fecha base: 1 de marzo 2025

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
# 0.  FUNCIONES FINANCIERAS PURAS (sin librerías externas)
# ══════════════════════════════════════════════════════════════

def _npv(rate: float, cf: np.ndarray) -> float:
    """VAN con convención Excel: todos los flujos se descuentan a partir de t=1."""
    t = np.arange(1, len(cf) + 1, dtype=float)
    return float(np.sum(cf / (1.0 + rate) ** t))


# Tasa de financiamiento para MIRR (tasa del préstamo = 8.5%)
TASA_FINANCIAMIENTO = 0.085


def _mirr(cf: np.ndarray, reinvest_rate: float) -> float:
    """
    MIRR replicando exactamente =MIRR(flujos, finance_rate=8.5%, reinvest_rate) del xlsx.
    Convención Excel:
      - PV de negativos: descontados con finance_rate desde t=0
      - FV de positivos: acumulados con reinvest_rate hasta t=n-1
      - Exponente: 1/(n-1) donde n = número de períodos
    """
    n = len(cf)
    finance_rate = TASA_FINANCIAMIENTO
    neg = np.where(cf < 0, cf, 0.0)
    pos = np.where(cf > 0, cf, 0.0)
    pv_neg = sum(neg[t] / (1 + finance_rate) ** t       for t in range(n))
    fv_pos = sum(pos[t] * (1 + reinvest_rate) ** (n-1-t) for t in range(n))
    if pv_neg >= 0 or fv_pos <= 0:
        return float("nan")
    return (fv_pos / (-pv_neg)) ** (1.0 / (n - 1)) - 1.0


# ══════════════════════════════════════════════════════════════
# 1.  DATOS BASE  (extraídos del xlsx NEUQUEN_BARILOCHE)
# ══════════════════════════════════════════════════════════════
#
# Años de concesión: 1–10 (2026–2035).
# Índice 0 = año inicio concesión (Y0: puesta en valor + crédito).
# Los arrays tienen 11 elementos [0..10].
# NOTA: el xlsx muestra 20 columnas pero solo Y1-Y9 tienen valores > 0;
#        Y10 completa el último año de cobro de peaje.

YEARS = 10

# ── Tarifa base y tránsito ─────────────────────────────────────
# Tarifa base sin IVA: $6.000 por UTEQ
TARIFA_BASE = 6_000.0          # ARS por UTEQ, sin IVA
AL_IVA_BASE = 0.21
TARIFA_IVA  = TARIFA_BASE * (1 + AL_IVA_BASE)

# UTEQUIs base (2023): 3.701.609 UTEQs/año
UTEQ_BASE_2023 = 3_701_609.393
# Año 1: crece 5% sobre la base
UTEQ_ARRANQUE = UTEQ_BASE_2023 * 1.05   # ≈ 3.886.690 UTEQs (= UTEQ del año 1)

# Crecimiento base: 5% año 1, luego 3% anual constante
TRAFICO_CRECIMIENTO_Y1   = 0.05   # fijo, no sensibilizable
TRAFICO_CRECIMIENTO_BASE = 0.03   # aplicable Y2 en adelante

# ── Ingresos de peaje con IVA (del sheet FLUJO) ────────────────
# Y0: sin ingresos de peaje (puesta en valor)
# Y1: 0 según el xlsx (el primer año la concesión no genera ingresos de peaje)
# Y2–Y10: ingresos crecientes
PEAJE_BASE = np.array([
    0,                        # Y0 (puesta en valor)
    0,                        # Y1 (sin ingresos de peaje en el xlsx)
    24_019_743_351.507931,    # Y2
    24_740_335_652.053169,    # Y3
    25_482_545_721.614765,    # Y4
    26_247_022_093.263210,    # Y5
    27_034_432_756.061108,    # Y6
    27_845_465_738.742943,    # Y7
    28_680_829_710.905231,    # Y8
    29_541_254_602.232388,    # Y9
    30_427_492_240.299358,    # Y10
], dtype=float)

# ── CAPEX con IVA (del sheet FLUJO / CAPEX) ───────────────────
# Y0: Obras de Puesta en Valor
# Y3–Y8: Gastos de Repavimentación
CAPEX_BASE = np.array([
    7_844_137_500.000000,    # Y0 – Obras de Puesta en Valor
    0,                       # Y1
    0,                       # Y2
    6_536_781_250.000000,    # Y3
    13_073_562_500.000000,   # Y4
    13_073_562_500.000000,   # Y5
    13_073_562_500.000000,   # Y6
    13_073_562_500.000000,   # Y7
    6_536_781_250.000000,    # Y8
    0,                       # Y9
    0,                       # Y10
], dtype=float)

# Desglose de CAPEX para sensibilidades
PUESTA_VALOR = np.array([7_844_137_500.0] + [0]*10, dtype=float)
OBRAS_OBLIG  = np.zeros(YEARS + 1, dtype=float)   # Sin obras obligatorias en este proyecto
REPAV = np.array([
    0, 0, 0,
    6_536_781_250.0,
    13_073_562_500.0,
    13_073_562_500.0,
    13_073_562_500.0,
    13_073_562_500.0,
    6_536_781_250.0,
    0, 0,
], dtype=float)

# ── OPEX con IVA – Conservación y Mantenimiento ────────────────
# Constante en todos los años (Y0–Y9), Y10 también
OPEX_CONSERVACION_BASE = 6_536_781_250.0
OPEX_BASE = np.full(YEARS + 1, OPEX_CONSERVACION_BASE)

# ── Amortización deuda (del sheet FLUJO) ──────────────────────
# Sistema Francés, tasa 8.5%, 6 cuotas, con un año de gracia
# Cuota anual: $1.205.839.713,96 (excepto Y2 que incluye gastos admin)
AMORT_DEUDA_BASE = np.array([
    0,                       # Y0
    0,                       # Y1 (año de gracia)
    1_260_748_676.455678,    # Y2 (cuota + gastos administrativos)
    1_205_839_713.955678,    # Y3
    1_205_839_713.955678,    # Y4
    1_205_839_713.955678,    # Y5
    1_205_839_713.955678,    # Y6
    1_205_839_713.955678,    # Y7
    0, 0, 0,
], dtype=float)

# ── Garantías anuales ──────────────────────────────────────────
GARANTIAS = np.full(YEARS + 1, 14_000_000.0)
GARANTIAS[0] = 14_000_000.0   # También en Y0

# ── Impuestos BASE por componente (del sheet IMPUESTOS/FLUJO) ──

# IVA a pagar (saldo neto IVA débito – IVA crédito)
IMP_IVA_BASE = np.array([
    0,                       # Y0 (IVA crédito > débito, no hay pago)
    0,                       # Y1
    865_127_024.158216,      # Y2
    2_175_874_191.745283,    # Y3
    1_194_870_874.347480,    # Y4
    1_354_311_267.953561,    # Y5
    1_520_006_820.559514,    # Y6
    1_692_270_302.446630,    # Y7
    2_988_128_570.918875,    # Y8
    4_271_941_207.016976,    # Y9
    4_425_751_045.028599,    # Y10
], dtype=float)

IMP_GANANCIAS_BASE = np.array([
    0,                       # Y0
    0,                       # Y1
    1_764_587_797.871494,    # Y2
    3_974_402_124.068939,    # Y3
    3_447_068_902.403382,    # Y4
    2_927_917_509.365389,    # Y5
    2_468_129_759.172087,    # Y6
    1_777_352_732.401003,    # Y7
    1_789_185_465.492349,    # Y8
    2_783_310_214.507095,    # Y9
    3_784_569_052.066667,    # Y10
], dtype=float)

IMP_IB_BASE = np.array([
    0,
    0,
    496_275_689.080742,      # Y2
    511_163_959.753165,      # Y3
    526_498_878.545760,      # Y4
    542_293_844.902132,      # Y5
    558_562_660.249196,      # Y6
    575_319_540.056672,      # Y7
    592_579_126.258373,      # Y8
    610_356_500.046124,      # Y9
    628_667_195.047507,      # Y10
], dtype=float)

IMP_MUNICIPAL_BASE = np.array([
    0,
    0,
    99_255_137.816148,       # Y2
    102_232_791.950633,      # Y3
    105_299_775.709152,      # Y4
    108_458_768.980426,      # Y5
    111_712_532.049839,      # Y6
    115_063_908.011334,      # Y7
    118_515_825.251675,      # Y8
    122_071_300.009225,      # Y9
    125_733_439.009501,      # Y10
], dtype=float)

IMP_SELLOS_BASE = np.array([
    145_213_785.123967,      # Y0
    145_213_785.123967,      # Y1
    145_213_785.123967,      # Y2
    145_213_785.123967,      # Y3
    145_213_785.123967,      # Y4
    0, 0, 0, 0, 0, 0,        # Y5–Y10
], dtype=float)

IMP_DBCR_BASE = np.array([
    65_890_755.000000,       # Y0
    0,                       # Y1
    288_236_920.218095,      # Y2
    296_884_027.824638,      # Y3
    305_790_548.659377,      # Y4
    314_964_265.119159,      # Y5
    324_413_193.072733,      # Y6
    334_145_588.864915,      # Y7
    344_169_956.530863,      # Y8
    354_495_055.226789,      # Y9
    365_129_906.883592,      # Y10
], dtype=float)

# ── Parámetros de amortización impositiva ─────────────────────
# Se usa la variante de 10 años para obras y 5 años para repavimentaciones
# (opción 2 del xlsx, que coincide con los valores de IMPUESTOS BASE)
AMORT_IMP_BASE = np.array([
    648_275_826.446281,      # Y0
    648_275_826.446281,      # Y1
    1_728_735_537.190082,    # Y2
    3_889_654_958.677685,    # Y3
    6_050_574_380.165288,    # Y4
    8_211_493_801.652890,    # Y5
    10_912_643_078.512394,   # Y6
    11_632_949_552.341595,   # Y7
    9_472_030_130.853993,    # Y8
    7_311_110_709.366388,    # Y9
    0,                       # Y10
], dtype=float)

# ── Intereses deducibles del préstamo (30% deducible) ─────────
# Solo aplican Y3–Y8 (mientras dura el préstamo, con gracia Y1)
INT_DEDUCIBLES_BASE = np.array([
    0,
    0,
    466_726_181.250000,      # Y2
    403_901_530.970017,      # Y3
    335_736_785.416236,      # Y4
    261_778_036.490384,      # Y5
    181_532_793.905834,      # Y6
    94_466_705.701597,       # Y7
    0, 0, 0,
], dtype=float)

# ── Alícuotas base ────────────────────────────────────────────
AL_GANANCIAS_BASE = 0.35
AL_IB_BASE        = 0.025
AL_MUNICIPAL_BASE = 0.005
AL_SELLOS_BASE    = 0.012
AL_DBCR_BASE      = 0.012
AL_IVA_CAPEX      = 0.21
AL_IVA_OPEX       = 0.11   # IVA ponderado sobre gastos operativos
AL_IVA_CONSERV    = 0.15   # IVA sobre Conservación y Mantenimiento

# ── Ingresos crédito LP (solo Y0) ─────────────────────────────
INGRESO_CREDITO = np.zeros(YEARS + 1)
INGRESO_CREDITO[0] = 5_490_896_250.000000

# ── Tasa VAN base ─────────────────────────────────────────────
TASA_VAN_BASE = 0.10


# ══════════════════════════════════════════════════════════════
# 2.  MODELO DE SENSIBILIDAD
# ══════════════════════════════════════════════════════════════

def run_model(
    delta_capex_repav   = 0.0,   # % variación repavimentación
    delta_opex          = 0.0,   # % variación OPEX total
    delta_trafico       = 0.0,   # delta pp sobre tasa crecimiento base (Y3+)
    tarifa              = TARIFA_BASE,   # tarifa sin IVA (ARS por UTEQ)
    al_ganancias        = AL_GANANCIAS_BASE,
    al_ib               = AL_IB_BASE,
    al_municipal        = AL_MUNICIPAL_BASE,
    al_sellos           = AL_SELLOS_BASE,
    al_dbcr             = AL_DBCR_BASE,
    al_iva_peaje        = AL_IVA_BASE,
    tasa_van            = TASA_VAN_BASE,
):
    # ── Tráfico ─────────────────────────────────────────────────
    # Y0 = 0 (puesta en valor)
    # Y1 = tránsito arranque (UTEQ_BASE_2023 × 1.05)  — sin ingresos de peaje
    # Y2 = UTEQ_ARRANQUE × (1 + 3%)
    # Y3+ = crece a tasa base 3% + Δ
    uteq = np.zeros(YEARS + 1)
    uteq[0] = 0.0
    uteq[1] = UTEQ_ARRANQUE
    tasa_eff = TRAFICO_CRECIMIENTO_BASE + delta_trafico
    tasa_eff = max(tasa_eff, -0.50)
    for y in range(2, YEARS + 1):
        uteq[y] = uteq[y - 1] * (1 + tasa_eff)

    # ── Ingresos de peaje con IVA ───────────────────────────────
    tarifa_con_iva = tarifa * (1 + al_iva_peaje)
    peaje = np.zeros(YEARS + 1)
    peaje[0] = 0.0
    peaje[1] = 0.0   # Año 1: sin ingresos (igual que xlsx)
    for y in range(2, YEARS + 1):
        peaje[y] = uteq[y] * tarifa_con_iva

    # Factor de tráfico para escalar impuestos proporcionales
    # Normalizamos contra el uteq del CASO BASE para que en base factor=1.0
    uteq_ref_for_tax = np.zeros(YEARS + 1)
    for y in range(2, YEARS + 1):
        uteq_base_y = UTEQ_ARRANQUE * ((1 + TRAFICO_CRECIMIENTO_BASE) ** (y - 1))
        uteq_ref_for_tax[y] = uteq[y] / uteq_base_y if uteq_base_y > 0 else 1.0

    total_ingresos = peaje + INGRESO_CREDITO

    # ── CAPEX escalado ──────────────────────────────────────────
    # En Neuquén-Bariloche no hay obras obligatorias, solo puesta en valor + repav
    capex = PUESTA_VALOR + REPAV * (1 + delta_capex_repav)

    # ── OPEX escalado ───────────────────────────────────────────
    opex = OPEX_BASE * (1 + delta_opex)

    # ── Impuestos escalados ─────────────────────────────────────
    factor_tarifa      = tarifa / TARIFA_BASE
    factor_trafico_avg = uteq_ref_for_tax * factor_tarifa
    # Para Y0 y Y1 no hay ingresos de peaje → factor=1 (el DBCR Y0 escala solo por tarifa implícita)
    factor_trafico_avg[0] = 1.0
    factor_trafico_avg[1] = 1.0

    imp_iva       = IMP_IVA_BASE      * factor_trafico_avg * ((1 + al_iva_peaje) / (1 + AL_IVA_BASE))
    imp_ib        = IMP_IB_BASE       * factor_trafico_avg * (al_ib       / AL_IB_BASE)
    imp_municipal = IMP_MUNICIPAL_BASE* factor_trafico_avg * (al_municipal / AL_MUNICIPAL_BASE)
    imp_sellos    = IMP_SELLOS_BASE   * (al_sellos / AL_SELLOS_BASE)
    imp_dbcr      = IMP_DBCR_BASE     * factor_trafico_avg * (al_dbcr     / AL_DBCR_BASE)
    imp_dbcr[0]   = IMP_DBCR_BASE[0] * (al_dbcr / AL_DBCR_BASE)   # Y0: DBCR sobre Crédito LP

    # ── Impuesto a las Ganancias ────────────────────────────────
    # Base imponible implícita del xlsx
    bi_base = np.where(AL_GANANCIAS_BASE > 0,
                       IMP_GANANCIAS_BASE / AL_GANANCIAS_BASE, 0.0)
    # Gastos que escalan con OPEX
    gastos_base_gan = OPEX_BASE / (1 + AL_IVA_OPEX) + GARANTIAS
    bi_ingr_base    = bi_base + gastos_base_gan
    bi_ingr_sen     = bi_ingr_base * factor_trafico_avg
    gastos_sen      = opex / (1 + AL_IVA_OPEX) + GARANTIAS

    base_imponible = bi_ingr_sen - gastos_sen

    # Quebrantos acumulados + impuesto
    quebranto_acum = np.zeros(YEARS + 1)
    imp_ganancias  = np.zeros(YEARS + 1)
    for y in range(1, YEARS + 1):
        base_y = base_imponible[y] + quebranto_acum[y - 1]
        if base_y <= 0:
            quebranto_acum[y] = base_y
            imp_ganancias[y]  = 0.0
        else:
            quebranto_acum[y] = 0.0
            imp_ganancias[y]  = base_y * al_ganancias

    total_impuestos = imp_iva + imp_ganancias + imp_ib + imp_municipal + imp_sellos + imp_dbcr

    # ── Egresos totales ─────────────────────────────────────────
    total_egresos = capex + opex + AMORT_DEUDA_BASE + total_impuestos + GARANTIAS

    # ── Flujo neto ──────────────────────────────────────────────
    flujo = total_ingresos - total_egresos

    # ── Métricas ────────────────────────────────────────────────
    # VAN/MIRR calculados sobre los 10 años (Y0..Y9) — igual que xlsx
    flujo_n    = flujo[:YEARS]
    egresos_n  = total_egresos[:YEARS]
    ingresos_n = total_ingresos[:YEARS]
    van        = _npv(tasa_van, flujo_n)
    van_egr    = _npv(tasa_van, egresos_n)
    van_ing    = _npv(tasa_van, ingresos_n)
    vaff_vae   = van / van_egr if van_egr != 0 else float("nan")
    mirr_val   = _mirr(flujo_n, tasa_van)
    acum       = np.cumsum(flujo)

    # Payback de obras: año en que el flujo acumulado cubre la inversión total
    inversion_obras = float(np.sum(PUESTA_VALOR) + np.sum(REPAV * (1 + delta_capex_repav)))
    payback = next((y + 1 for y, v in enumerate(acum) if v >= inversion_obras), None)

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
        mirr            = mirr_val,
        payback         = payback,
        inversion_obras = inversion_obras,
        uteq            = uteq,
    )


# ══════════════════════════════════════════════════════════════
# 3.  CONSTANTES BASE (calculadas dinámicamente)
# ══════════════════════════════════════════════════════════════

_base_calc    = run_model()
MIRR_BASE     = _base_calc["mirr"]
VAN_BASE      = _base_calc["van"]
VAFF_VAE_BASE = _base_calc["vaff_vae"]


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

/* KPI cards */
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

/* Sidebar section headers */
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

    # ── Tránsito y Tarifa ──────────────────────────────────────
    st.markdown('<div class="sh">🚗 Tránsito y Tarifa</div>', unsafe_allow_html=True)

    tarifa_input = st.number_input(
        "Tarifa base (ARS)",
        min_value=1_000, max_value=50_000,
        value=int(TARIFA_BASE), step=10,
        help=f"Tarifa base del xlsx: $ {TARIFA_BASE:,.0f}. Se aplica desde el Año 2."
    )

    st.caption(
        "📌 **Regla de ingresos:**  \n"
        "**Año 1** → tránsito de arranque (UTEQs base × 1.05), sin ingresos.  \n"
        "**Año 2+** → crece a tasa base 3% + Δ abajo."
    )

    delta_trafico_pp = st.slider(
        "Δ tasa crecimiento anual Año 2+ (±pp sobre base 3%)",
        min_value=-3.0, max_value=5.0, value=0.0, step=0.01,
        format="%.2f pp",
        help="Afecta al Año 2 en adelante. Tasa base: 3% anual."
    )
    delta_trafico = delta_trafico_pp / 100

    # ── CAPEX ──────────────────────────────────────────────────
    st.markdown('<div class="sh">🏗️ CAPEX – Repavimentación</div>', unsafe_allow_html=True)
    st.caption("⚠️ Este proyecto no tiene obras obligatorias adicionales a la puesta en valor.")
    delta_repav = st.slider(
        "Repavimentación (%)",
        min_value=-40, max_value=100, value=0, step=1,
        help="Variación % sobre el monto base de repavimentaciones (Años 3–8)"
    ) / 100

    # ── OPEX ──────────────────────────────────────────────────
    st.markdown('<div class="sh">⚙️ OPEX – Conservación y Mantenimiento</div>', unsafe_allow_html=True)
    delta_opex = st.slider(
        "Variación OPEX (%)",
        min_value=-40, max_value=100, value=0, step=1
    ) / 100

    # ── Impuestos ─────────────────────────────────────────────
    st.markdown('<div class="sh">💰 Alícuotas impositivas</div>', unsafe_allow_html=True)
    al_ganancias = st.slider(
        "Ganancias (%)", 0.0, 55.0, 35.0, 0.1,
        format="%.1f %%",
        help="Base: 35%"
    ) / 100
    al_ib = st.slider(
        "Ingresos Brutos (%)", 0.0, 10.0, 2.5, 0.1,
        format="%.1f %%",
        help="Base: 2.5%"
    ) / 100
    al_municipal = st.slider(
        "Tasas Municipales (%)", 0.0, 3.0, 0.5, 0.1,
        format="%.1f %%",
        help="Base: 0.5%"
    ) / 100
    al_sellos = st.slider(
        "Impuesto de Sellos (%)", 0.0, 5.0, 1.2, 0.1,
        format="%.1f %%",
        help="Base: 1.2% (primeros 5 años)"
    ) / 100
    al_dbcr = st.slider(
        "Débitos y Créditos Bancarios (%)", 0.0, 5.0, 1.2, 0.1,
        format="%.1f %%",
        help="Base: 1.2%"
    ) / 100
    al_iva_peaje = st.slider(
        "IVA sobre peaje (%)", 0, 27, 21, 1,
        help="Base: 21%"
    ) / 100

    # ── Tasa de descuento ─────────────────────────────────────
    st.markdown('<div class="sh">📐 Tasa de descuento VAN</div>', unsafe_allow_html=True)
    tasa_van = st.slider(
        "Tasa de descuento (%)", 5.0, 25.0, 10.0, 0.1,
        format="%.1f %%"
    ) / 100

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

YEARS_RANGE = list(range(2025, 2025 + YEARS + 1))   # 2025..2035


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
    cls  = "pos" if good else "neg"
    sgn  = "+" if d > 0 else ""
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
C = dict(
    pos="#3ecf8e", neg="#f76e6e",
    acc="#6c7fe8", warn="#f0a742",
    pur="#a855f7", gry="#64748b",
)


# ══════════════════════════════════════════════════════════════
# 5.  ENCABEZADO Y KPIs
# ══════════════════════════════════════════════════════════════
st.markdown("# 🏔️ NEUQUÉN – BARILOCHE — Análisis de Sensibilidades")
st.markdown(
    "Concesión vial 10 años · 2026–2035 &nbsp;|&nbsp; "
    "Longitud: 360.65 km &nbsp;|&nbsp; "
    "Modificá los parámetros en el panel ← para ver el impacto en tiempo real"
)
st.divider()

c1, c2, c3, c4 = st.columns(4)
mirr_s   = f"{sc['mirr']:.2%}"    if not np.isnan(sc["mirr"])     else "n/d"
vaff_s   = f"{sc['vaff_vae']:.2%}" if not np.isnan(sc["vaff_vae"]) else "n/d"
pb_año   = sc["payback"]
pb_s     = f"Año {pb_año}  ({2025 + pb_año})" if pb_año is not None else "No recupera"
inv_obras_s = fmt_ars(sc["inversion_obras"])

# Orden: VAFF/VAE  |  VAN  |  TIR Modificada  |  Payback
c1.markdown(kpi("VAFF / VAE", vaff_s,
                sc["vaff_vae"], VAFF_VAE_BASE), unsafe_allow_html=True)
c2.markdown(kpi(f"VAN  (tasa {tasa_van:.0%})", fmt_ars(sc["van"]),
                sc["van"], VAN_BASE), unsafe_allow_html=True)
c3.markdown(kpi("TIR Modificada (MIRR)", mirr_s,
                sc["mirr"], MIRR_BASE), unsafe_allow_html=True)
c4.markdown(kpi(f"Payback obras · {inv_obras_s}", pb_s, 0, 0),
            unsafe_allow_html=True)

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
            "Composición de Egresos por año  ($ MM ARS)",
            "Ingresos vs Egresos  ($ MM ARS)",
        ],
        vertical_spacing=0.16, horizontal_spacing=0.10,
    )

    bc = [C["pos"] if v >= 0 else C["neg"] for v in sc["flujo"]]
    fig.add_trace(go.Bar(x=YEARS_RANGE, y=sc["flujo"]/1e9,
                         marker_color=bc, name="Flujo Neto"),
                  row=1, col=1)
    fig.add_hline(y=0, line_dash="dot", line_color="#888", row=1, col=1)

    fig.add_trace(go.Scatter(
        x=YEARS_RANGE, y=sc["acum"]/1e9, mode="lines+markers",
        line=dict(color=C["acc"], width=2.5), marker=dict(size=5),
        fill="tozeroy", fillcolor="rgba(108,127,232,.12)", name="Acumulado"),
        row=1, col=2)
    fig.add_hline(y=0, line_dash="dot", line_color="#888", row=1, col=2)

    # Egresos apilados
    fig.add_trace(go.Bar(x=YEARS_RANGE, y=sc["capex"]/1e9,
                         name="CAPEX", marker_color=C["neg"]), row=2, col=1)
    fig.add_trace(go.Bar(x=YEARS_RANGE, y=sc["opex"]/1e9,
                         name="OPEX", marker_color=C["warn"]), row=2, col=1)
    fig.add_trace(go.Bar(x=YEARS_RANGE, y=sc["total_imp"]/1e9,
                         name="Impuestos", marker_color=C["pur"]), row=2, col=1)
    fig.add_trace(go.Bar(x=YEARS_RANGE, y=sc["amort_deuda"]/1e9,
                         name="Deuda LP", marker_color=C["gry"]), row=2, col=1)

    fig.add_trace(go.Scatter(x=YEARS_RANGE, y=sc["total_ing"]/1e9,
                              mode="lines", line=dict(color=C["pos"], width=2.5),
                              name="Ingresos"), row=2, col=2)
    fig.add_trace(go.Scatter(x=YEARS_RANGE, y=sc["total_egr"]/1e9,
                              mode="lines", line=dict(color=C["neg"], width=2.5),
                              name="Egresos"), row=2, col=2)

    fig.update_layout(**PL, barmode="stack", height=640, showlegend=True,
                      legend=dict(orientation="h", y=-0.07,
                                  bgcolor="rgba(0,0,0,0)"))
    for ax in ["xaxis","xaxis2","xaxis3","xaxis4",
               "yaxis","yaxis2","yaxis3","yaxis4"]:
        fig.update_layout(**{ax: dict(gridcolor="#252f45", zeroline=False)})

    st.plotly_chart(fig, use_container_width=True)


# ─────────────────────────────────────────────────────────────
# TAB 2 – TORNADO + SPIDER
# ─────────────────────────────────────────────────────────────
with tab2:
    st.markdown("#### Gráfico Tornado — impacto individual sobre el VAN")
    st.caption("Cada barra aplica un shock de ±20% a UNA sola variable, manteniendo el resto en el valor del panel.")

    BASE_KW = dict(
        delta_capex_repav=delta_repav,
        delta_opex=delta_opex, delta_trafico=delta_trafico,
        tarifa=float(tarifa_input),
        al_ganancias=al_ganancias, al_ib=al_ib,
        al_municipal=al_municipal, al_sellos=al_sellos,
        al_dbcr=al_dbcr, al_iva_peaje=al_iva_peaje, tasa_van=tasa_van,
    )

    shocks = {
        "Repavim. +20%":      dict(delta_capex_repav=delta_repav+0.20),
        "Repavim. –20%":      dict(delta_capex_repav=delta_repav-0.20),
        "OPEX +20%":          dict(delta_opex=delta_opex+0.20),
        "OPEX –20%":          dict(delta_opex=delta_opex-0.20),
        "Tránsito +1pp":      dict(delta_trafico=delta_trafico+0.01),
        "Tránsito –1pp":      dict(delta_trafico=delta_trafico-0.01),
        "Tarifa +20%":        dict(tarifa=float(tarifa_input)*1.20),
        "Tarifa –20%":        dict(tarifa=float(tarifa_input)*0.80),
        "Ganancias +10pp":    dict(al_ganancias=min(0.60, al_ganancias+0.10)),
        "Ganancias –10pp":    dict(al_ganancias=max(0.00, al_ganancias-0.10)),
        "IB +2pp":            dict(al_ib=al_ib+0.02),
        "IB –2pp":            dict(al_ib=max(0, al_ib-0.02)),
        "IVA peaje +3pp":     dict(al_iva_peaje=al_iva_peaje+0.03),
        "IVA peaje –3pp":     dict(al_iva_peaje=max(0, al_iva_peaje-0.03)),
        "Db/Cr +1pp":         dict(al_dbcr=al_dbcr+0.01),
        "Db/Cr –1pp":         dict(al_dbcr=max(0, al_dbcr-0.01)),
        "Tasa descuento +2pp":dict(tasa_van=tasa_van+0.02),
        "Tasa descuento –2pp":dict(tasa_van=max(0.01, tasa_van-0.02)),
    }

    base_van = sc["van"]
    t_rows = []
    for label, ov in shocks.items():
        r = run_model(**{**BASE_KW, **ov})
        t_rows.append({"Variable": label,
                        "ΔVAN": (r["van"] - base_van) / 1e9})
    df_t = pd.DataFrame(t_rows).sort_values("ΔVAN")

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
        "CAPEX Repavim.": lambda p: dict(delta_capex_repav=delta_repav + p/100),
        "OPEX":           lambda p: dict(delta_opex=delta_opex + p/100),
        "Tránsito (+pp)": lambda p: dict(delta_trafico=delta_trafico + p/100),
        "Tarifa (+%)":    lambda p: dict(tarifa=float(tarifa_input) * (1 + p/100)),
        "Ganancias (+pp)":lambda p: dict(al_ganancias=max(0, al_ganancias + p/100)),
    }
    cols_spider = [C["warn"], C["pur"], C["pos"], C["acc"], C["neg"]]

    fig3 = go.Figure()
    for (vname, fn), col in zip(variables.items(), cols_spider):
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
    fig3.update_layout(**PL, height=400,
                       margin=dict(t=40, b=50, l=60, r=20),
                       legend=dict(bgcolor="rgba(0,0,0,0)"))
    fig3.update_xaxes(title_text="Variación (%)")
    fig3.update_yaxes(title_text="MIRR (%)")
    st.plotly_chart(fig3, use_container_width=True)


# ─────────────────────────────────────────────────────────────
# TAB 3 – MAPAS DE CALOR
# ─────────────────────────────────────────────────────────────
with tab3:

    trafico_rng = np.arange(-2.0, 3.5, 0.5)   # Δpp sobre base 3%
    repav_rng   = np.arange(-30, 55, 10)        # % variación repavimentación
    opex_rng    = np.arange(-30, 55, 10)
    gan_rng     = np.arange(15, 55, 5)
    tasa_rng    = np.arange(6, 20, 2)

    def heat(**ov):
        return run_model(**{**BASE_KW, **ov})

    # ── Mapa 1: MIRR = Δtráfico × Repavimentación ────────────
    st.markdown("#### MIRR (%) — Δ Tránsito (pp) × Repavimentación CAPEX (%)")
    mat1 = np.zeros((len(trafico_rng), len(repav_rng)))
    for i, tr in enumerate(trafico_rng):
        for j, rp in enumerate(repav_rng):
            r = heat(delta_trafico=delta_trafico+tr/100,
                     delta_capex_repav=delta_repav+rp/100)
            mat1[i, j] = r["mirr"]*100 if not np.isnan(r["mirr"]) else 0

    fig4 = go.Figure(go.Heatmap(
        z=mat1.round(1),
        x=[f"{c:+d}%" for c in repav_rng],
        y=[f"{t:+.1f}pp" for t in trafico_rng],
        colorscale="RdYlGn", text=mat1.round(1),
        texttemplate="%{text:.1f}%",
        colorbar=dict(title="MIRR (%)", tickfont=dict(color="#c5cdd8")),
    ))
    fig4.update_layout(**PL, height=370, margin=dict(t=30,b=60,l=100,r=20))
    fig4.update_xaxes(title_text="Variación Repavimentación CAPEX")
    fig4.update_yaxes(title_text="Δ crecimiento tránsito")
    st.plotly_chart(fig4, use_container_width=True)

    # ── Mapa 2: VAN = Δtráfico × OPEX ────────────────────────
    st.markdown("#### VAN ($ MM) — Δ Tránsito × OPEX (%)")
    mat2 = np.zeros((len(trafico_rng), len(opex_rng)))
    for i, tr in enumerate(trafico_rng):
        for j, op in enumerate(opex_rng):
            r = heat(delta_trafico=delta_trafico+tr/100,
                     delta_opex=delta_opex+op/100)
            mat2[i, j] = r["van"] / 1e9

    fig5 = go.Figure(go.Heatmap(
        z=mat2.round(1),
        x=[f"{o:+d}%" for o in opex_rng],
        y=[f"{t:+.1f}pp" for t in trafico_rng],
        colorscale="RdYlGn", text=mat2.round(1),
        texttemplate="%{text:.0f}",
        colorbar=dict(title="VAN (MM$)", tickfont=dict(color="#c5cdd8")),
    ))
    fig5.update_layout(**PL, height=370, margin=dict(t=30,b=60,l=100,r=20))
    fig5.update_xaxes(title_text="Variación OPEX")
    fig5.update_yaxes(title_text="Δ crecimiento tránsito")
    st.plotly_chart(fig5, use_container_width=True)

    # ── Mapa 3: VAN = tasa descuento × Repavimentación ───────
    st.markdown("#### VAN ($ MM) — Tasa de descuento × Repavimentación CAPEX (%)")
    mat3 = np.zeros((len(tasa_rng), len(repav_rng)))
    for i, td in enumerate(tasa_rng):
        for j, rp in enumerate(repav_rng):
            r = heat(tasa_van=td/100, delta_capex_repav=delta_repav+rp/100)
            mat3[i, j] = r["van"] / 1e9

    fig6 = go.Figure(go.Heatmap(
        z=mat3.round(1),
        x=[f"{c:+d}%" for c in repav_rng],
        y=[f"{t}%" for t in tasa_rng],
        colorscale="RdYlGn", text=mat3.round(1),
        texttemplate="%{text:.0f}",
        colorbar=dict(title="VAN (MM$)", tickfont=dict(color="#c5cdd8")),
    ))
    fig6.update_layout(**PL, height=370, margin=dict(t=30,b=60,l=80,r=20))
    fig6.update_xaxes(title_text="Variación Repavimentación CAPEX")
    fig6.update_yaxes(title_text="Tasa de descuento")
    st.plotly_chart(fig6, use_container_width=True)

    # ── Mapa 4: VAFF/VAE = Δtráfico × Ganancias ──────────────
    st.markdown("#### VAFF/VAE — Δ Tránsito × Alícuota Ganancias (%)")
    mat4 = np.zeros((len(trafico_rng), len(gan_rng)))
    for i, tr in enumerate(trafico_rng):
        for j, ga in enumerate(gan_rng):
            r = heat(delta_trafico=delta_trafico+tr/100,
                     al_ganancias=ga/100)
            mat4[i, j] = r["vaff_vae"] if not np.isnan(r["vaff_vae"]) else 0

    fig7 = go.Figure(go.Heatmap(
        z=mat4.round(4),
        x=[f"{g}%" for g in gan_rng],
        y=[f"{t:+.1f}pp" for t in trafico_rng],
        colorscale="RdYlGn", text=mat4.round(3),
        texttemplate="%{text:.3f}",
        colorbar=dict(title="VAFF/VAE", tickfont=dict(color="#c5cdd8")),
    ))
    fig7.update_layout(**PL, height=370, margin=dict(t=30,b=60,l=100,r=20))
    fig7.update_xaxes(title_text="Alícuota Ganancias")
    fig7.update_yaxes(title_text="Δ crecimiento tránsito")
    st.plotly_chart(fig7, use_container_width=True)


# ── FOOTER ────────────────────────────────────────────────────
st.divider()
st.caption(
    "NEUQUÉN–BARILOCHE (GESTIÓN–MIT) · Modelo de sensibilidades · "
    "Flujos base tomados del xlsx al 1° de marzo 2025 · "
    "Concesión 10 años (2026–2035) · Longitud: 360.65 km · "
    "No incluye recálculo de préstamo ni WACC."
)
