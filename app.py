
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import json

st.set_page_config(page_title="Belgian Demographics", layout="wide", page_icon="🇧🇪")

@st.cache_data
def load_data():
    muni = pd.read_parquet("muni_choropleth.parquet")
    region = pd.read_parquet("region_data.parquet")
    with open("belgium_municipalities.geojson") as f:
        geo = json.load(f)
    return muni, region, geo

muni_pivot, df_region_long, geojson = load_data()

st.sidebar.title("🇧🇪 Belgian Demographics")
st.sidebar.markdown("Population by nationality, 1992–2025")
tab = st.sidebar.radio("View", ["Choropleth map", "Population composition", "Age breakdown", "Gender ratio heatmap"])

if tab == "Choropleth map":
    st.title("Non-Belgian population share by municipality")
    col1, col2 = st.columns([3, 1])
    with col2:
        year = st.slider("Year", 2009, 2025, 2025)
        max_pct = st.slider("Color scale max (%)", 10, 80, 40)
        region_filter = st.multiselect("Filter by region",
            muni_pivot["TX_RGN_DESCR_NL"].unique().tolist(),
            default=muni_pivot["TX_RGN_DESCR_NL"].unique().tolist())
    df_map = muni_pivot[
        (muni_pivot["year"] == year) &
        (muni_pivot["TX_RGN_DESCR_NL"].isin(region_filter))
    ].copy()
    df_map["total"] = df_map["BEL"] + df_map["ETR"]
    df_map["pct_etr"] = (df_map["ETR"] / df_map["total"] * 100).round(1)
    df_map["CD_REFNIS"] = df_map["CD_REFNIS"].astype(str)
    fig = px.choropleth(
        df_map, geojson=geojson, locations="CD_REFNIS",
        featureidkey="properties.NSI_CODE", color="pct_etr",
        hover_name="TX_DESCR_NL",
        hover_data={"total": ":,", "ETR": ":,", "pct_etr": ":.1f", "CD_REFNIS": False},
        color_continuous_scale="OrRd", range_color=[0, max_pct],
        labels={"pct_etr": "% non-Belgian"})
    fig.update_geos(fitbounds="locations", visible=False)
    fig.update_layout(margin={"r":0,"t":0,"l":0,"b":0}, height=580)
    with col1:
        st.plotly_chart(fig, use_container_width=True)
    st.subheader("Top 10 municipalities by non-Belgian share")
    top10 = df_map.nlargest(10, "pct_etr")[["TX_DESCR_NL","TX_PROV_DESCR_NL","BEL","ETR","total","pct_etr"]]
    top10.columns = ["Municipality","Province","Belgians","Non-Belgians","Total","% Non-Belgian"]
    st.dataframe(top10, use_container_width=True, hide_index=True)

elif tab == "Population composition":
    st.title("Belgian vs non-Belgian population over time")
    col1, col2 = st.columns([1, 3])
    with col1:
        region = st.selectbox("Region", ["All Belgium",
            "Flanders region", "Brussels-Capital region", "Walloon region"])
        mode = st.radio("View", ["Absolute", "Percentage"])
    df = df_region_long[
        (df_region_long["Gender"].isin(["Women", "Men"])) &
        (df_region_long["Marital Status"].isna()) &
        (df_region_long["Age Group"].isna()) &
        (df_region_long["Nationality"].isin(["Belgians", "non-Belgians"]))
    ]
    if region != "All Belgium":
        df = df[df["Region"] == region]
    df = df.groupby(["year", "Nationality"])["population"].sum().reset_index()
    if mode == "Percentage":
        total = df.groupby("year")["population"].sum().reset_index(name="total")
        df = df.merge(total, on="year")
        df["population"] = (df["population"] / df["total"] * 100).round(1)
    fig = px.area(df, x="year", y="population", color="Nationality",
        color_discrete_map={"Belgians": "#185FA5", "non-Belgians": "#D85A30"},
        labels={"population": "%" if mode == "Percentage" else "Population", "year": "Year"})
    fig.update_layout(hovermode="x unified", margin={"t": 20})
    with col2:
        st.plotly_chart(fig, use_container_width=True)
    latest = df[df["year"] == df["year"].max()]
    m1, m2, m3 = st.columns(3)
    non_bel = latest[latest["Nationality"] == "non-Belgians"]["population"].values[0]
    bel = latest[latest["Nationality"] == "Belgians"]["population"].values[0]
    first_non = df[(df["year"] == df["year"].min()) & (df["Nationality"] == "non-Belgians")]["population"].values[0]
    if mode == "Absolute":
        m1.metric("Non-Belgians (latest)", f"{non_bel/1e6:.2f}M")
        m2.metric("Belgians (latest)", f"{bel/1e6:.2f}M")
        m3.metric("Non-Belgian growth", f"+{((non_bel-first_non)/first_non*100):.0f}%")
    else:
        m1.metric("Non-Belgian share (latest)", f"{non_bel:.1f}%")
        m2.metric("Belgian share (latest)", f"{bel:.1f}%")
        m3.metric("Non-Belgian share in 1992", f"{first_non:.1f}%")

elif tab == "Age breakdown":
    st.title("Age distribution — Belgians vs non-Belgians")
    col1, col2 = st.columns([1, 3])
    with col1:
        year = st.slider("Year", 1992, 2025, 2025)
    df = df_region_long[
        (df_region_long["Gender"].isin(["Women", "Men"])) &
        (df_region_long["Nationality"].isin(["Belgians", "non-Belgians"])) &
        (df_region_long["Age Group"].notna()) &
        (df_region_long["Marital Status"].notna())
    ]
    yr_list = sorted(df["year"].unique())
    nearest = min(yr_list, key=lambda y: abs(y - year))
    df = df[df["year"] == nearest]
    df = df.groupby(["Nationality", "Age Group"])["population"].sum().reset_index()
    age_order = ["Less than 18 years", "From 18 to 64 years", "65 years and more"]
    fig = px.bar(df, x="Age Group", y="population", color="Nationality",
        barmode="group", category_orders={"Age Group": age_order},
        color_discrete_map={"Belgians": "#185FA5", "non-Belgians": "#D85A30"},
        labels={"population": "Population", "Age Group": ""},
        title=f"Age breakdown in {nearest}")
    fig.update_layout(margin={"t": 40}, hovermode="x unified")
    fig.update_yaxes(tickformat=".2s")
    with col2:
        st.plotly_chart(fig, use_container_width=True)

elif tab == "Gender ratio heatmap":
    st.title("Gender ratio in non-Belgian population (M/F)")
    st.caption("Values above 1.0 = more men than women. Indicates labor migration patterns.")
    col1, col2 = st.columns([1, 3])
    with col1:
        year = st.slider("Year", 1992, 2025, 2025)
    df = df_region_long[
        (df_region_long["Gender"].isin(["Women", "Men"])) &
        (df_region_long["Nationality"] == "non-Belgians") &
        (df_region_long["Age Group"].notna()) &
        (df_region_long["Marital Status"].notna())
    ]
    yr_list = sorted(df["year"].unique())
    nearest = min(yr_list, key=lambda y: abs(y - year))
    df = df[df["year"] == nearest]
    df = df.groupby(["Region", "Age Group", "Gender"])["population"].sum().reset_index()
    pivot = df.pivot_table(index="Region", columns=["Age Group", "Gender"], values="population")
    age_groups = ["Less than 18 years", "From 18 to 64 years", "65 years and more"]
    age_labels = ["<18", "18-64", "65+"]
    ratios, texts, hover = [], [], []
    for ag, al in zip(age_groups, age_labels):
        row_r, row_t, row_h = [], [], []
        for region in pivot.index:
            try:
                m = pivot.loc[region, (ag, "Men")]
                f = pivot.loc[region, (ag, "Women")]
                ratio = round(m / f, 2)
                row_r.append(ratio)
                row_t.append(str(ratio))
                row_h.append(f"M: {int(m):,}<br>F: {int(f):,}<br>Ratio: {ratio}")
            except:
                row_r.append(None)
                row_t.append("N/A")
                row_h.append("N/A")
        ratios.append(row_r)
        texts.append(row_t)
        hover.append(row_h)
    fig = go.Figure(data=go.Heatmap(
        z=ratios, x=list(pivot.index), y=age_labels,
        text=texts, hovertext=hover,
        hovertemplate="%{hovertext}<extra></extra>",
        texttemplate="%{text}",
        colorscale=[[0,"#D85A30"],[0.5,"#f5f5f5"],[1,"#185FA5"]],
        zmid=1.0, zmin=0.7, zmax=1.3,
        colorbar=dict(title="M/F ratio")))
    fig.update_layout(margin={"t": 20}, height=300)
    with col2:
        st.plotly_chart(fig, use_container_width=True)
