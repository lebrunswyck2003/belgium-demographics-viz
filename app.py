
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import json, copy

st.set_page_config(
    page_title="Belgian Demographics 1992-2025",
    layout="wide",
    page_icon="🇧🇪"
)

MERGER_MAP = {
    "12041": ["12030","12034"],
    "23106": ["23023","23024","23032"],
    "37021": ["37007","37018"],
    "37022": ["37012","37015"],
    "44083": ["44001","44011"],
    "44084": ["44012","44029"],
    "44085": ["44034","44036","44072","44080"],
    "44086": ["44048","44012"],
    "44087": ["44045","44073"],
    "44088": ["44040","44043","44049"],
    "45068": ["45041","45059"],
    "46029": ["46003","46025"],
    "46030": ["46013","46021","46024"],
    "55085": ["55022","55039"],
    "55086": ["55004","55035"],
    "57096": ["57064"],
    "57097": ["57027","57062"],
    "71071": ["71066","71070"],
    "71072": ["71002","71016","71022","71047","71053"],
    "72042": ["72018","72039"],
    "72043": ["72020","72029"],
    "73110": ["73006","73009"],
    "73111": ["73022","73066"],
    "82039": ["82003","82005"],
}

@st.cache_data
def load_data():
    muni = pd.read_parquet("muni_choropleth.parquet")
    region = pd.read_parquet("region_data.parquet")
    with open("belgium_municipalities.geojson") as f:
        geo = json.load(f)
    return muni, region, geo

@st.cache_data
def build_geo_with_mergers(merger_map_json):
    _, _, geo = load_data()
    merger_map = json.loads(merger_map_json)
    geo_new = copy.deepcopy(geo)
    nsi_to_feature = {f["properties"]["NSI_CODE"]: f for f in geo_new["features"]}
    for new_code, old_codes in merger_map.items():
        found = [c for c in old_codes if c in nsi_to_feature]
        if found:
            # Duplicate first matching old feature with new code
            new_feat = copy.deepcopy(nsi_to_feature[found[0]])
            new_feat["properties"]["NSI_CODE"] = new_code
            geo_new["features"].append(new_feat)
    return geo_new

muni_pivot, df_region_long, geojson = load_data()
geojson = build_geo_with_mergers(json.dumps(MERGER_MAP))

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.title("🇧🇪 Belgian Demographics")
    st.caption("Population by nationality · StatBel · CC BY 4.0")
    st.divider()
    tab = st.radio("View", [
        "🗺️ Choropleth map",
        "📈 Population composition",
        "👥 Age breakdown",
        "⚧ Gender ratio heatmap",
        "🔄 Naturalization signals"
    ])
    st.divider()
    st.caption("Data: StatBel 1992–2025\nMunicipality level: 2009–2025")

# ── Choropleth ────────────────────────────────────────────────────────────────
if tab == "🗺️ Choropleth map":
    st.header("Non-Belgian population share by municipality")
    st.caption("Share of non-Belgian residents (ETR) as % of total municipal population")

    col_ctrl, col_map = st.columns([1, 3])
    with col_ctrl:
        year = st.slider("Year", 2009, 2025, 2025)
        max_pct = st.slider("Color scale max (%)", 10, 80, 40)
        region_filter = st.multiselect(
            "Filter by region",
            muni_pivot["TX_RGN_DESCR_NL"].unique().tolist(),
            default=muni_pivot["TX_RGN_DESCR_NL"].unique().tolist()
        )
        search = st.text_input("Search municipality", "")

    df_map = muni_pivot[
        (muni_pivot["year"] == year) &
        (muni_pivot["TX_RGN_DESCR_NL"].isin(region_filter))
    ].copy()
    df_map["total"] = df_map["BEL"] + df_map["ETR"]
    df_map["pct_etr"] = (df_map["ETR"] / df_map["total"] * 100).round(1)
    df_map["CD_REFNIS"] = df_map["CD_REFNIS"].astype(str)

    fig = px.choropleth(
        df_map,
        geojson=geojson,
        locations="CD_REFNIS",
        featureidkey="properties.NSI_CODE",
        color="pct_etr",
        hover_name="TX_DESCR_NL",
        hover_data={
            "total": ":,",
            "ETR": ":,",
            "pct_etr": ":.1f",
            "CD_REFNIS": False
        },
        color_continuous_scale="OrRd",
        range_color=[0, max_pct],
        labels={"pct_etr": "% non-Belgian"}
    )
    fig.update_geos(fitbounds="locations", visible=False)
    fig.update_layout(
        margin={"r": 0, "t": 0, "l": 0, "b": 0},
        height=600,
        paper_bgcolor="rgba(0,0,0,0)",
        geo=dict(bgcolor="rgba(0,0,0,0)")
    )

    with col_map:
        st.plotly_chart(fig, use_container_width=True)

    st.divider()
    col_t1, col_t2 = st.columns(2)
    with col_t1:
        st.subheader("Top 10 — highest non-Belgian share")
        top10 = df_map.nlargest(10, "pct_etr")[
            ["TX_DESCR_NL", "TX_PROV_DESCR_NL", "BEL", "ETR", "total", "pct_etr"]
        ]
        top10.columns = ["Municipality", "Province", "Belgians", "Non-Belgians", "Total", "% Non-Belgian"]
        st.dataframe(top10, use_container_width=True, hide_index=True)
    with col_t2:
        st.subheader("Top 10 — fastest growing non-Belgian share")
        if year > 2009:
            df_prev = muni_pivot[muni_pivot["year"] == year - 1].copy()
            df_prev["total"] = df_prev["BEL"] + df_prev["ETR"]
            df_prev["pct_prev"] = (df_prev["ETR"] / df_prev["total"] * 100).round(1)
            df_prev["CD_REFNIS"] = df_prev["CD_REFNIS"].astype(str)
            df_growth = df_map.merge(
                df_prev[["CD_REFNIS", "pct_prev"]], on="CD_REFNIS", how="left"
            )
            df_growth["change"] = (df_growth["pct_etr"] - df_growth["pct_prev"]).round(2)
            top_growth = df_growth.nlargest(10, "change")[
                ["TX_DESCR_NL", "TX_PROV_DESCR_NL", "pct_prev", "pct_etr", "change"]
            ]
            top_growth.columns = ["Municipality", "Province", "% prev year", "% this year", "Change (pp)"]
            st.dataframe(top_growth, use_container_width=True, hide_index=True)
        else:
            st.info("Select a year after 2009 to see growth comparison.")

    if search:
        st.divider()
        st.subheader(f"Search results for '{search}'")
        results = df_map[df_map["TX_DESCR_NL"].str.contains(search, case=False, na=False)]
        if len(results):
            st.dataframe(
                results[["TX_DESCR_NL", "TX_PROV_DESCR_NL", "BEL", "ETR", "total", "pct_etr"]],
                use_container_width=True, hide_index=True
            )
        else:
            st.warning("No municipalities found.")

# ── Population composition ────────────────────────────────────────────────────
elif tab == "📈 Population composition":
    st.header("Belgian vs non-Belgian population over time")
    st.caption("Full time series 1992–2025 from StatBel regional data")

    col_ctrl, col_chart = st.columns([1, 3])
    with col_ctrl:
        region = st.selectbox("Region", [
            "All Belgium",
            "Flanders region",
            "Brussels-Capital region",
            "Walloon region"
        ])
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
        df["population"] = (df["population"] / df["total"] * 100).round(2)

    fig = px.area(
        df, x="year", y="population", color="Nationality",
        color_discrete_map={"Belgians": "#185FA5", "non-Belgians": "#D85A30"},
        labels={"population": "%" if mode == "Percentage" else "Population", "year": "Year"}
    )
    fig.update_layout(hovermode="x unified", margin={"t": 20}, height=420)
    fig.update_traces(line=dict(width=1.5))

    with col_chart:
        st.plotly_chart(fig, use_container_width=True)

    latest_year = df["year"].max()
    first_year = df["year"].min()
    latest = df[df["year"] == latest_year]
    first = df[df["year"] == first_year]

    non_bel_latest = latest[latest["Nationality"] == "non-Belgians"]["population"].values[0]
    bel_latest = latest[latest["Nationality"] == "Belgians"]["population"].values[0]
    non_bel_first = first[first["Nationality"] == "non-Belgians"]["population"].values[0]

    m1, m2, m3 = st.columns(3)
    if mode == "Absolute":
        m1.metric("Non-Belgians (latest)", f"{non_bel_latest/1e6:.2f}M",
                  delta=f"+{((non_bel_latest-non_bel_first)/non_bel_first*100):.0f}% since {first_year}")
        m2.metric("Belgians (latest)", f"{bel_latest/1e6:.2f}M")
        m3.metric("Non-Belgian share", f"{non_bel_latest/(non_bel_latest+bel_latest)*100:.1f}%")
    else:
        m1.metric("Non-Belgian share (latest)", f"{non_bel_latest:.1f}%")
        m2.metric("Belgian share (latest)", f"{bel_latest:.1f}%")
        m3.metric(f"Non-Belgian share in {first_year}", f"{non_bel_first:.1f}%")

# ── Age breakdown ─────────────────────────────────────────────────────────────
elif tab == "👥 Age breakdown":
    st.header("Age distribution — Belgians vs non-Belgians")
    st.caption("Compares age structure between Belgian and non-Belgian populations")

    col_ctrl, col_chart = st.columns([1, 3])
    with col_ctrl:
        year = st.slider("Year", 1992, 2025, 2025)
        region = st.selectbox("Region", [
            "All regions",
            "Flanders region",
            "Brussels-Capital region",
            "Walloon region"
        ])

    df = df_region_long[
        (df_region_long["Gender"].isin(["Women", "Men"])) &
        (df_region_long["Nationality"].isin(["Belgians", "non-Belgians"])) &
        (df_region_long["Age Group"].notna()) &
        (df_region_long["Marital Status"].notna())
    ]
    if region != "All regions":
        df = df[df["Region"] == region]

    yr_list = sorted(df["year"].unique())
    nearest = min(yr_list, key=lambda y: abs(y - year))
    if nearest != year:
        st.info(f"Showing {nearest} (closest available year)")

    df = df[df["year"] == nearest]
    df = df.groupby(["Nationality", "Age Group"])["population"].sum().reset_index()

    # Add percentage within each nationality
    totals = df.groupby("Nationality")["population"].sum().reset_index(name="nat_total")
    df = df.merge(totals, on="Nationality")
    df["pct"] = (df["population"] / df["nat_total"] * 100).round(1)

    age_order = ["Less than 18 years", "From 18 to 64 years", "65 years and more"]

    col_abs, col_pct = st.columns(2)
    with col_abs:
        fig1 = px.bar(df, x="Age Group", y="population", color="Nationality",
            barmode="group", category_orders={"Age Group": age_order},
            color_discrete_map={"Belgians": "#185FA5", "non-Belgians": "#D85A30"},
            labels={"population": "Population", "Age Group": ""},
            title="Absolute numbers")
        fig1.update_layout(margin={"t": 40}, hovermode="x unified", height=380)
        fig1.update_yaxes(tickformat=".2s")
        st.plotly_chart(fig1, use_container_width=True)

    with col_pct:
        fig2 = px.bar(df, x="Age Group", y="pct", color="Nationality",
            barmode="group", category_orders={"Age Group": age_order},
            color_discrete_map={"Belgians": "#185FA5", "non-Belgians": "#D85A30"},
            labels={"pct": "% within nationality", "Age Group": ""},
            title="Share within each nationality")
        fig2.update_layout(margin={"t": 40}, hovermode="x unified", height=380)
        fig2.update_yaxes(ticksuffix="%")
        st.plotly_chart(fig2, use_container_width=True)

# ── Gender ratio heatmap ──────────────────────────────────────────────────────
elif tab == "⚧ Gender ratio heatmap":
    st.header("Gender ratio in non-Belgian population (M/F)")
    st.caption("Values above 1.0 = more men than women · Indicates labor migration vs family settlement patterns")

    col_ctrl, col_chart = st.columns([1, 3])
    with col_ctrl:
        year = st.slider("Year", 1992, 2025, 2025)
        show_belgians = st.checkbox("Also show Belgian ratio", value=False)

    df = df_region_long[
        (df_region_long["Gender"].isin(["Women", "Men"])) &
        (df_region_long["Age Group"].notna()) &
        (df_region_long["Marital Status"].notna())
    ]
    if not show_belgians:
        df = df[df["Nationality"] == "non-Belgians"]

    yr_list = sorted(df["year"].unique())
    nearest = min(yr_list, key=lambda y: abs(y - year))
    if nearest != year:
        st.info(f"Showing {nearest} (closest available year)")

    df = df[df["year"] == nearest]
    nat_col = "Nationality" if show_belgians else None

    df_agg = df.groupby(
        ["Region", "Age Group", "Gender"] + ([nat_col] if nat_col else [])
    )["population"].sum().reset_index()

    age_groups = ["Less than 18 years", "From 18 to 64 years", "65 years and more"]
    age_labels = ["<18", "18–64", "65+"]
    regions = sorted(df_agg["Region"].unique())

    nats = df_agg["Nationality"].unique() if show_belgians else ["non-Belgians"]

    for nat in nats:
        if show_belgians:
            st.subheader(nat)
            df_nat = df_agg[df_agg["Nationality"] == nat]
        else:
            df_nat = df_agg

        pivot = df_nat.pivot_table(
            index="Region", columns=["Age Group", "Gender"], values="population"
        )

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
            z=ratios,
            x=list(pivot.index),
            y=age_labels,
            text=texts,
            hovertext=hover,
            hovertemplate="%{hovertext}<extra></extra>",
            texttemplate="%{text}",
            colorscale=[[0, "#D85A30"], [0.5, "#f5f5f5"], [1, "#185FA5"]],
            zmid=1.0, zmin=0.7, zmax=1.3,
            colorbar=dict(title="M/F ratio")
        ))
        fig.update_layout(margin={"t": 20}, height=320)
        with col_chart:
            st.plotly_chart(fig, use_container_width=True)

# ── Naturalization signals ────────────────────────────────────────────────────
elif tab == "🔄 Naturalization signals":
    st.header("Naturalization signals by municipality")
    st.caption(
        "Municipalities where non-Belgian population decreased while total population "
        "remained stable or grew — a signal of naturalization activity"
    )

    col_ctrl, col_chart = st.columns([1, 3])
    with col_ctrl:
        year_from = st.slider("From year", 2009, 2023, 2015)
        year_to = st.slider("To year", year_from + 1, 2025, 2025)
        min_pop = st.slider("Min. total population", 1000, 50000, 5000, step=1000)

    df_from = muni_pivot[muni_pivot["year"] == year_from].copy()
    df_to = muni_pivot[muni_pivot["year"] == year_to].copy()

    df_from["total"] = df_from["BEL"] + df_from["ETR"]
    df_to["total"] = df_to["BEL"] + df_to["ETR"]
    df_from["pct_etr"] = (df_from["ETR"] / df_from["total"] * 100).round(1)
    df_to["pct_etr"] = (df_to["ETR"] / df_to["total"] * 100).round(1)

    df_merged = df_from[["CD_REFNIS", "TX_DESCR_NL", "TX_PROV_DESCR_NL",
                          "TX_RGN_DESCR_NL", "total", "ETR", "pct_etr"]].merge(
        df_to[["CD_REFNIS", "total", "ETR", "pct_etr"]],
        on="CD_REFNIS", suffixes=("_from", "_to")
    )

    df_merged = df_merged[df_merged["total_to"] >= min_pop]
    df_merged["total_change"] = df_merged["total_to"] - df_merged["total_from"]
    df_merged["etr_change"] = df_merged["ETR_to"] - df_merged["ETR_from"]
    df_merged["pct_change"] = (df_merged["pct_etr_to"] - df_merged["pct_etr_from"]).round(1)

    # Signal: non-Belgian share decreased AND total population stable or grew
    signals = df_merged[
        (df_merged["pct_change"] < -1) &
        (df_merged["total_change"] >= 0)
    ].sort_values("pct_change")

    m1, m2, m3 = st.columns(3)
    m1.metric("Municipalities with signal", len(signals))
    m2.metric("Avg. non-Belgian share drop", f"{signals['pct_change'].mean():.1f}pp" if len(signals) else "—")
    m3.metric("Period", f"{year_from} → {year_to}")

    with col_chart:
        if len(signals) > 0:
            fig = px.scatter(
                signals,
                x="total_change",
                y="pct_change",
                size="total_to",
                color="TX_RGN_DESCR_NL",
                hover_name="TX_DESCR_NL",
                hover_data={
                    "TX_PROV_DESCR_NL": True,
                    "pct_etr_from": ":.1f",
                    "pct_etr_to": ":.1f",
                    "pct_change": ":.1f",
                    "TX_RGN_DESCR_NL": False
                },
                labels={
                    "total_change": "Total population change",
                    "pct_change": "Change in non-Belgian share (pp)",
                    "TX_RGN_DESCR_NL": "Region"
                },
                title=f"Naturalization signals: {year_from} → {year_to}",
                color_discrete_map={
                    "Vlaams Gewest": "#185FA5",
                    "Brussels Hoofdstedelijk Gewest": "#D85A30",
                    "Waals Gewest": "#1D9E75"
                }
            )
            fig.add_hline(y=0, line_dash="dash", line_color="gray", opacity=0.5)
            fig.add_vline(x=0, line_dash="dash", line_color="gray", opacity=0.5)
            fig.update_layout(height=480, margin={"t": 40})
            st.plotly_chart(fig, use_container_width=True)

            st.subheader("Top candidates for naturalization activity")
            display = signals.head(20)[
                ["TX_DESCR_NL", "TX_PROV_DESCR_NL", "pct_etr_from",
                 "pct_etr_to", "pct_change", "total_change"]
            ]
            display.columns = ["Municipality", "Province", f"% non-Bel {year_from}",
                                f"% non-Bel {year_to}", "Change (pp)", "Pop. change"]
            st.dataframe(display, use_container_width=True, hide_index=True)
        else:
            st.info("No municipalities match the naturalization signal criteria for this period.")
