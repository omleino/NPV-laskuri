import streamlit as st
import numpy as np
import pandas as pd
import altair as alt

st.set_page_config(page_title="Maalämpö NPV – herkkyys 0–4 %", layout="wide")

# ---------- Helpers ----------
def npv(rate: float, cashflows: list[float]) -> float:
    """Diskontattu nettonykyarvo (NPV) kassavirroille. t=0 on cashflows[0]."""
    return sum(cf / ((1 + rate) ** t) for t, cf in enumerate(cashflows))

def build_savings_cf(
    years: int,
    dh_annual_cost_now: float,     # €/v tänään
    elec_price_now: float,         # €/kWh (tai €/MWh – kunhan yksiköt sopivat kulutuksen kanssa)
    gshp_annual_elec_use: float,   # kWh/v (tai MWh/v sopivin yksiköin)
    dh_growth: float,              # esim. 0.02
    elec_growth: float,            # esim. 0.03
    ml_monthly_cost: float = 0.0   # €/kk kiinteä kustannus (huolto/palvelu)
):
    """
    Palauttaa listan vuosittaisista nettoSÄÄSTÖistä (DH − [ML sähkö + ML kiinteä kk-maksu]),
    pituus = years (vuodet 1..years).
    """
    cfs = []
    fixed_yearly = ml_monthly_cost * 12
    for y in range(1, years + 1):
        dh_cost_y = dh_annual_cost_now * ((1 + dh_growth) ** (y - 1))
        elec_price_y = elec_price_now * ((1 + elec_growth) ** (y - 1))
        ml_operating_y = gshp_annual_elec_use * elec_price_y + fixed_yearly
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
ml_monthly_cost = st.sidebar.number_input("Maalämmön kuukausikustannus (€/kk)", value=0.0, step=10.0, format="%.2f")

st.sidebar.subheader("Investointi")
ml_capex = st.sidebar.number_input("Maalämmön investointi (t=0, €)", value=250000.0, step=5000.0, format="%.2f")

st.sidebar.markdown("---")
st.sidebar.caption("Huom: yksiköiden tulee sopia yhteen (esim. €/kWh ja kWh/v).")

# ---------- Title & intro ----------
st.title("NPV: Maalämpö vs. Kaukolämpö – herkkyys 0–4 %")
st.write(
    "Taulukossa esitetään **NPV (B−A)**, jossa B = maalämpö (säästöt suhteessa kaukolämpöön) ja A = investointi. "
    "Rivit: sähkön hinnan kasvu 0–4 %. Sarakkeet: kaukolämmön hinnan kasvu 0–4 %. "
    "Maalämmön **kuukausikustannus** on mukana vuosittaisissa käyttökuluissa (12 × €/kk)."
)

# ---------- Build the 5×5 NPV table (0–4 %) ----------
elec_growths = [0.00, 0.01, 0.02, 0.03, 0.04]
dh_growths   = [0.00, 0.01, 0.02, 0.03, 0.04]

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
            elec_growth=eg,
            ml_monthly_cost=ml_monthly_cost
        )
        cfs = [-abs(ml_capex)] + savings  # t=0 investointi + vuosittaiset säästöt
        row.append(npv(rate_pct, cfs))
    npv_matrix.append(row)

index_labels = [f"Sähkö {int(g*100)} %" for g in elec_growths]
column_labels = [f"KL {int(g*100)} %" for g in dh_growths]

df = pd.DataFrame(npv_matrix, index=index_labels, columns=column_labels)

# ---------- NPV Table ----------
st.subheader("NPV-taulukko (€, B−A)")
# Yritetään näyttää tyyliteltynä; jos ei onnistu, näytetään ilman gradienttia.
try:
    import matplotlib  # noqa: F401
    styled = (
        df.style
        .format(lambda x: euro_fmt(x, 0))
        .background_gradient(axis=None)
    )
    st.dataframe(styled, use_container_width=True)
except Exception:
    st.dataframe(df.applymap(lambda x: euro_fmt(x, 0)), use_container_width=True)

# ---------- Heatmap ----------
st.subheader("Lämpökartta: NPV (€, B−A)")
df_heat = df.copy()
df_heat["Sähkön kasvu"] = df_heat.index
df_heat = df_heat.melt(id_vars="Sähkön kasvu", var_name="Kaukolämmön kasvu", value_name="NPV (€)")

heat = alt.Chart(df_heat).mark_rect().encode(
    x=alt.X("Kaukolämmön kasvu:N", title="Kaukolämmön hinnan kasvu"),
    y=alt.Y("Sähkön kasvu:N", title="Sähkön hinnan kasvu"),
    color=alt.Color("NPV (€):Q", scale=alt.Scale(scheme="redyellowgreen", domainMid=0)),
    tooltip=[
        alt.Tooltip("Sähkön kasvu:N", title="Sähkön hinta, kasvu"),
        alt.Tooltip("Kaukolämmön kasvu:N", title="Kaukolämmön hinta, kasvu"),
        alt.Tooltip("NPV (€):Q", format=",.0f", title="NPV (€)")
    ]
).properties(height=420)
st.altair_chart(heat, use_container_width=True)

# ---------- Quick summary ----------
npv_base = df.loc["Sähkö 0 %", "KL 0 %"]
pos_share = (df.values > 0).sum() / df.size
st.markdown(
    f"**Pikatieto:** 0 % / 0 % -kasvuilla NPV = **{euro_fmt(npv_base, 0)}**. "
    f"Positiivisia soluja: **{pos_share:.0%}**."
)

st.markdown("---")
st.caption(
    "NPV lasketaan: t=0 investointi (neg.) + vuosittaiset säästöt (kaukolämpö − maalämmön sähkökulut − maalämmön kiinteä kk-maksu × 12). "
    "Kasvuprosentit vaikuttavat **hintakehitykseen** (€/v ja €/kWh), eivät kulutukseen."
)
