import streamlit as st
import numpy as np
import pandas as pd
import altair as alt

st.set_page_config(page_title="Maalämpö NPV – herkkyys 1–4 %", layout="wide")

# ---------- Helpers ----------
def npv(rate: float, cashflows: list[float]) -> float:
    return sum(cf / ((1 + rate) ** t) for t, cf in enumerate(cashflows))

def build_savings_cf(
    years: int,
    dh_annual_cost_now: float,     # €/v today
    elec_price_now: float,         # €/kWh (or €/MWh – kunhan yksiköt sopivat kulutuksen kanssa)
    gshp_annual_elec_use: float,   # kWh/v (tai MWh/v sopivin yksiköin)
    dh_growth: float,              # esim. 0.02
    elec_growth: float,            # esim. 0.03
):
    """Palauttaa listan vuosittaisista nettoSÄÄSTÖistä (DH − ML sähkö), pituus years (vuodet 1..years)."""
    cfs = []
    for y in range(1, years + 1):
        dh_cost_y = dh_annual_cost_now * ((1 + dh_growth) ** (y - 1))
        elec_price_y = elec_price_now * ((1 + elec_growth) ** (y - 1))
        ml_operating_y = gshp_annual_elec_use * elec_price_y
        saving_y = dh_cost_y - ml_operating_y
        cfs.append(saving_y)
    return cfs

def euro_fmt(x, decimals: int = 0) -> str:
    """Muotoilu: tuhannet välilyönnillä, desimaalit pilkulla, perään ' €'."""
    try:
        s = f"{x:,.{decimals}f}".replace(",", " ").replace(".", ",")
        return s + " €"
    except Exception:
        return f"{x} €"

# ---------- Sidebar inputs ----------
st.sidebar.title("Syötteet")

st.sidebar.subheader("Perusparametrit")
years = st.sidebar.number_input("Aika (vuotta)", 1, 50, 20, step=1)
rate_pct = st.sidebar.number_input("Diskonttauskorko (%)", -50.0, 100.0, 6.0, step=0.25) / 100.0

st.sidebar.subheader("Kustannukset tänään")
dh_annual_now = st.sidebar.number_input("Kaukolämmön vuosikustannus tänään (€/v)", value=40000.0, step=1000.0, format="%.2f")
elec_price_now = st.sidebar.number_input("Sähkön hinta tänään (€/kWh)", value=0.12, step=0.01, format="%.4f")
ml_elec_use = st.sidebar.number_input("Maalämmön sähkönkulutus (kWh/v)", value=120000.0, step=1000.0, format="%.2f")

st.sidebar.subheader("Investointi")
ml_capex = st.sidebar.number_input("Maalämmön investointi (t=0, €)", value=250000.0, step=5000.0, format="%.2f")

st.sidebar.markdown("---")
st.sidebar.caption("Huom: yksiköiden tulee sopia yhteen (esim. €/kWh ja kWh/v).")

st.title("NPV: Maalämpö vs. Kaukolämpö – herkkyys 1–4 %")
st.write(
    "Taulukossa esitetään **NPV (B−A)**, jossa B = maalämpö (säästöt suhteessa kaukolämpöön) ja A = investointi. "
    "Rivit: sähkön hinnan kasvu 1–4 %. Sarakkeet: kaukolämmön hinnan kasvu 1–4 %."
)

# ---------- Build the 4x4 NPV table ----------
elec_growths = [0.01, 0.02, 0.03, 0.04]
dh_growths   = [0.01, 0.02, 0.03, 0.04]

npv_matrix = []
for eg in elec_growths:
    row = []
    for dg in dh_growths:
        savings = build_savings_cf(
            years=years,
            dh_annual_cost_now=dh_annual_now,
            elec_price_now=elec_price_now,
            gshp_annual_elec_use=ml_elec_use,
            dh_growth=dg,
            elec_growth=eg
        )
        cfs = [-abs(ml_capex)] + savings  # t=0 investointi + vuosittaiset säästöt
        row.append(npv(rate_pct, cfs))
    npv_matrix.append(row)

df = pd.DataFrame(
    npv_matrix,
    index=[f"Sähkö {int(g*100)} %" for g in elec_growths],
    columns=[f"KL {int(g*100)} %" for g in dh_growths]
)

st.subheader("NPV-taulukko (€, B−A)")

# Turvallinen renderöinti: käytä gradienttia vain jos matplotlib löytyy
try:
    import matplotlib  # noqa: F401
    styled = (
        df.style
        .format(lambda x: euro_fmt(x, 0))
        .background_gradient(axis=None)
    )
    st.dataframe(styled, use_container_width=True)
except Exception:
    st.dataframe(df.style.format(lambda x: euro_fmt(x, 0)), use_container_width=True)

# ---------- Heatmap ----------
st.subheader("Lämpökartta: NPV (€, B−A)")
df_heat = df.reset_index().melt(id_vars=df.index.name or "index", var_name="Kaukolämmön kasvu", value_name="NPV (€)")
df_heat = df_heat.rename(columns={df.index_name if hasattr(df, 'index_name') else (df.index.name or "index"): "Sähkön kasvu"})

heat = alt.Chart(df_heat).mark_rect().encode(
    x=alt.X("Kaukolämmön kasvu:N", title="Kaukolämmön hinnan kasvu"),
    y=alt.Y("Sähkön kasvu:N", title="Sähkön hinnan kasvu"),
    color=alt.Color("NPV (€):Q", scale=alt.Scale(scheme="redyellowgreen")),
    tooltip=["Sähkön kasvu", "Kaukolämmön kasvu", alt.Tooltip("NPV (€):Q", format=",.0f", title="NPV (€)")]
).properties(height=420)
st.altair_chart(heat, use_container_width=True)

st.markdown("---")
st.caption(
    "NPV lasketaan: t=0 investointi (neg.) + vuosittaiset säästöt (kaukolämpö − maalämmön sähkökulut). "
    "Kasvu %:t vaikuttavat **hintakehitykseen** (€/v ja €/kWh), ei kulutukseen."
)
