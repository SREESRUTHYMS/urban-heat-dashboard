import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
import plotly.express as px
import plotly.graph_objects as go
from folium.plugins import HeatMap
import os

# ─────────────────────────────────────────────
#  PAGE CONFIG
# ─────────────────────────────────────────────
st.set_page_config(
    page_title="Urban Heat Exposure Dashboard",
    page_icon="🌡️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ─────────────────────────────────────────────
#  CUSTOM CSS
# ─────────────────────────────────────────────
st.markdown("""
<style>
    .metric-card {
        background: linear-gradient(135deg, #1e2130, #2a2f45);
        border: 1px solid #3a3f55;
        border-radius: 12px;
        padding: 20px;
        text-align: center;
        margin-bottom: 10px;
    }
    .metric-value {
        font-size: 2rem;
        font-weight: 700;
        color: #ff6b35;
    }
    .metric-label {
        font-size: 0.85rem;
        color: #a0a8c0;
        margin-top: 4px;
        text-transform: uppercase;
        letter-spacing: 1px;
    }
    .section-header {
        font-size: 1.2rem;
        font-weight: 600;
        color: #e0e4f0;
        border-left: 4px solid #ff6b35;
        padding-left: 12px;
        margin: 20px 0 12px 0;
    }
</style>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────
#  RISK COLOR MAP
# ─────────────────────────────────────────────
risk_colors = {
    "Very High Risk": "#7f1d1d",
    "High Risk":      "#ef4444",
    "Moderate Risk":  "#f97316",
    "Low Risk":       "#eab308",
    "Very Low Risk":  "#22c55e",
}

# ─────────────────────────────────────────────
#  DATA LOADERS — reads CSV files
# ─────────────────────────────────────────────

@st.cache_data
def load_hei_data():
    try:
        df = pd.read_csv("data/hei_export.csv")
        return df
    except Exception as e:
        st.warning(f"hei_export.csv load error: {e}")
        return pd.DataFrame()

@st.cache_data
def load_spatial_stats():
    try:
        df = pd.read_csv("data/heat_exposure_index.csv")
        stats = pd.DataFrame([{
            "total_pixels":     len(df),
            "mean_hei":         round(df["hei_score"].mean(), 4),
            "max_hei":          round(df["hei_score"].max(), 4),
            "min_hei":          round(df["hei_score"].min(), 4),
            "high_risk_count":  df["risk_class"].str.contains("high", case=False, na=False).sum(),
            "total_population": round(df["pop_raw"].sum(), 0),
        }])
        return stats
    except Exception as e:
        st.warning(f"heat_exposure_index.csv load error: {e}")
        return pd.DataFrame()

@st.cache_data
def load_lst_monthly():
    try:
        df = pd.read_csv("data/lst_monthly.csv")
        return df
    except Exception as e:
        st.warning(f"lst_monthly.csv load error: {e}")
        return pd.DataFrame()

@st.cache_data
def load_hei_risk_summary():
    try:
        return pd.read_csv("data/hei_risk_summary.csv")
    except Exception:
        return pd.DataFrame()

@st.cache_data
def load_lisa_clusters():
    try:
        df = pd.read_csv("data/lisa_clusters.csv")
        if "cluster_type" in df.columns:
            return df.groupby("cluster_type").size().reset_index(name="count")
        return df
    except Exception:
        return pd.DataFrame()

@st.cache_data
def load_cooling_zones():
    try:
        return pd.read_csv("data/cooling_zones.csv")
    except Exception:
        return pd.DataFrame()

@st.cache_data
def load_urban_morphology():
    try:
        return pd.read_csv("data/urban_morphology.csv")
    except Exception:
        return pd.DataFrame()

# ─────────────────────────────────────────────
#  SIDEBAR
# ─────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 🌡️ Urban Heat Dashboard")
    st.markdown("**Al-Ahsa 2025 — PostGIS + Streamlit**")
    st.markdown("---")

    df_raw = load_hei_data()

    if not df_raw.empty:
        st.markdown("### 🔍 Filters")

        risk_options = sorted(df_raw["risk_class"].dropna().unique().tolist())
        selected_risks = st.multiselect("Risk Class", risk_options, default=risk_options)

        hei_min = float(df_raw["hei_score"].min())
        hei_max = float(df_raw["hei_score"].max())
        hei_range = st.slider("HEI Score Range", hei_min, hei_max,
                              (hei_min, hei_max), step=0.01)

        lulc_options = sorted(df_raw["lulc_class"].dropna().unique().tolist())
        selected_lulc = st.multiselect("LULC Class", lulc_options, default=lulc_options)

        urban_options = sorted(df_raw["urban_class"].dropna().unique().tolist())
        selected_urban = st.multiselect("Urban Class", urban_options, default=urban_options)

        st.markdown("---")
        st.markdown("### 🗺️ Map Options")
        map_style = st.selectbox("Basemap",
            ["CartoDB positron", "CartoDB dark_matter", "OpenStreetMap"])
        show_heatmap = st.checkbox("Heatmap Layer", value=False)
        show_cooling = st.checkbox("Show Cooling Zones", value=False)

    else:
        selected_risks = []
        hei_range = (0.0, 1.0)
        selected_lulc = []
        selected_urban = []
        map_style = "CartoDB positron"
        show_heatmap = False
        show_cooling = False

    st.markdown("---")
    st.caption("Built with Streamlit + PostGIS · Urban_heat DB")

# ─────────────────────────────────────────────
#  APPLY FILTERS
# ─────────────────────────────────────────────
if not df_raw.empty and selected_risks and selected_lulc:
    df = df_raw[
        (df_raw["risk_class"].isin(selected_risks)) &
        (df_raw["hei_score"].between(hei_range[0], hei_range[1])) &
        (df_raw["lulc_class"].isin(selected_lulc)) &
        (df_raw["urban_class"].isin(selected_urban))
    ].copy()
else:
    df = pd.DataFrame()

# ─────────────────────────────────────────────
#  HEADER
# ─────────────────────────────────────────────
st.markdown("# 🌡️ Urban Heat Exposure Index Dashboard")
st.markdown("Spatial analysis of urban heat risk — PostGIS · Streamlit · Al-Ahsa 2025")
st.markdown("---")

tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "📊 Overview",
    "🗺️ Spatial Map",
    "📈 Analytics",
    "🌡️ LST Profile",
    "📋 Data Table"
])

# ══════════════════════════════════════════════
#  TAB 1 — OVERVIEW
# ══════════════════════════════════════════════
with tab1:
    stats = load_spatial_stats()

    if not stats.empty:
        s = stats.iloc[0]
        c1, c2, c3, c4, c5, c6 = st.columns(6)
        kpis = [
            (c1, f"{int(s['total_pixels']):,}",    "Total Pixels",        "#ff6b35"),
            (c2, f"{float(s['mean_hei']):.4f}",     "Mean HEI",            "#ff6b35"),
            (c3, f"{float(s['max_hei']):.4f}",      "Max HEI",             "#ef4444"),
            (c4, f"{int(s['high_risk_count']):,}",  "High Risk Pixels",    "#ef4444"),
            (c5, f"{int(s['total_population']):,}", "Population Exposed",  "#3b82f6"),
            (c6, "0.9947",                          "Moran's I",           "#22c55e"),
        ]
        for col, val, label, color in kpis:
            with col:
                st.markdown(f"""
                <div class="metric-card">
                    <div class="metric-value" style="color:{color}">{val}</div>
                    <div class="metric-label">{label}</div>
                </div>""", unsafe_allow_html=True)

    st.markdown("---")

    if not df.empty:
        r1, r2 = st.columns(2)

        with r1:
            st.markdown('<div class="section-header">📊 Risk Class Distribution</div>',
                        unsafe_allow_html=True)
            risk_counts = df["risk_class"].value_counts().reset_index()
            risk_counts.columns = ["Risk Class", "Count"]
            fig_pie = px.pie(
                risk_counts, names="Risk Class", values="Count",
                color="Risk Class", color_discrete_map=risk_colors, hole=0.45
            )
            fig_pie.update_layout(
                paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                font_color="#e0e4f0", margin=dict(t=20, b=20, l=10, r=10)
            )
            st.plotly_chart(fig_pie, use_container_width=True)

        with r2:
            st.markdown('<div class="section-header">🏙️ LULC Class Breakdown</div>',
                        unsafe_allow_html=True)
            lulc_counts = df["lulc_class"].value_counts().reset_index()
            lulc_counts.columns = ["LULC Class", "Count"]
            fig_lulc = px.bar(
                lulc_counts, x="Count", y="LULC Class", orientation="h",
                color="Count", color_continuous_scale="Oranges"
            )
            fig_lulc.update_layout(
                paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                font_color="#e0e4f0", coloraxis_showscale=False,
                yaxis=dict(autorange="reversed"), margin=dict(t=10, b=10)
            )
            st.plotly_chart(fig_lulc, use_container_width=True)

        risk_summary = load_hei_risk_summary()
        if not risk_summary.empty:
            st.markdown('<div class="section-header">📋 Risk Summary Table</div>',
                        unsafe_allow_html=True)
            st.dataframe(risk_summary, use_container_width=True, height=250)

        lisa = load_lisa_clusters()
        if not lisa.empty:
            st.markdown('<div class="section-header">🔵 LISA Spatial Cluster Types</div>',
                        unsafe_allow_html=True)
            fig_lisa = px.bar(
                lisa, x="cluster_type", y="count", color="cluster_type",
                color_discrete_sequence=px.colors.qualitative.Bold
            )
            fig_lisa.update_layout(
                paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                font_color="#e0e4f0", showlegend=False, margin=dict(t=10, b=10)
            )
            st.plotly_chart(fig_lisa, use_container_width=True)

# ══════════════════════════════════════════════
#  TAB 2 — SPATIAL MAP
# ══════════════════════════════════════════════
with tab2:
    st.markdown('<div class="section-header">🗺️ Interactive Spatial Map</div>',
                unsafe_allow_html=True)

    if not df.empty:
        center_lat = df["latitude"].mean()
        center_lon = df["longitude"].mean()

        m = folium.Map(location=[center_lat, center_lon], zoom_start=12, tiles=map_style)

        if show_heatmap:
            heat_data = df[["latitude", "longitude", "hei_score"]].dropna().values.tolist()
            HeatMap(heat_data, radius=15, blur=20, min_opacity=0.4).add_to(m)
        else:
            for _, row in df.iterrows():
                color = risk_colors.get(row.get("risk_class", ""), "#94a3b8")
                folium.CircleMarker(
                    location=[row["latitude"], row["longitude"]],
                    radius=5, color=color, fill=True,
                    fill_color=color, fill_opacity=0.8,
                    popup=folium.Popup(
                        f"<b>HEI:</b> {row['hei_score']:.4f}<br>"
                        f"<b>Risk:</b> {row['risk_class']}<br>"
                        f"<b>Pop:</b> {row['population']:.0f}<br>"
                        f"<b>NDVI:</b> {row['ndvi']:.4f}<br>"
                        f"<b>LST norm:</b> {row['lst_norm']:.4f}<br>"
                        f"<b>LULC:</b> {row['lulc_class']}<br>"
                        f"<b>Urban:</b> {row['urban_class']}",
                        max_width=220
                    )
                ).add_to(m)

        if show_cooling:
            cooling_df = load_cooling_zones()
            if not cooling_df.empty and "latitude" in cooling_df.columns:
                for _, row in cooling_df.iterrows():
                    folium.CircleMarker(
                        location=[row["latitude"], row["longitude"]],
                        radius=4, color="#22c55e", fill=True,
                        fill_color="#22c55e", fill_opacity=0.6,
                        popup="Cooling Zone"
                    ).add_to(m)

        legend_html = """
        <div style="position:fixed;bottom:30px;left:30px;z-index:1000;
             background:rgba(15,17,23,0.9);padding:12px 18px;
             border-radius:10px;border:1px solid #3a3f55;color:#e0e4f0;
             font-size:13px;line-height:1.8">
          <b>Risk Class</b><br>
          <span style="color:#7f1d1d">●</span> Very High Risk<br>
          <span style="color:#ef4444">●</span> High Risk<br>
          <span style="color:#f97316">●</span> Moderate Risk<br>
          <span style="color:#eab308">●</span> Low Risk<br>
          <span style="color:#22c55e">●</span> Very Low Risk
        </div>"""
        m.get_root().html.add_child(folium.Element(legend_html))
        st_folium(m, width=None, height=550)
    else:
        st.info("No data to display. Adjust your filters in the sidebar.")

# ══════════════════════════════════════════════
#  TAB 3 — ANALYTICS
# ══════════════════════════════════════════════
with tab3:
    if not df.empty:
        st.markdown('<div class="section-header">📈 HEI Score Distribution</div>',
                    unsafe_allow_html=True)
        c1, c2, c3 = st.columns(3)

        with c1:
            fig_hist = px.histogram(df, x="hei_score", nbins=40,
                color_discrete_sequence=["#ff6b35"], title="HEI Score Histogram")
            fig_hist.update_layout(paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)", font_color="#e0e4f0",
                margin=dict(t=40, b=20))
            st.plotly_chart(fig_hist, use_container_width=True)

        with c2:
            fig_scatter = px.scatter(df, x="ndvi", y="hei_score",
                color="risk_class", color_discrete_map=risk_colors,
                title="NDVI vs HEI Score",
                hover_data=["lulc_class", "population"])
            fig_scatter.update_layout(paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)", font_color="#e0e4f0",
                margin=dict(t=40, b=20))
            st.plotly_chart(fig_scatter, use_container_width=True)

        with c3:
            fig_box = px.box(df, x="risk_class", y="hei_score",
                color="risk_class", color_discrete_map=risk_colors,
                title="HEI Score by Risk Class")
            fig_box.update_layout(paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)", font_color="#e0e4f0",
                margin=dict(t=40, b=20), showlegend=False)
            st.plotly_chart(fig_box, use_container_width=True)

        st.markdown("---")

        st.markdown('<div class="section-header">⚖️ HEI Component Averages by Risk Class</div>',
                    unsafe_allow_html=True)
        components = (df.groupby("risk_class")[["lst_norm","pop_norm","ndvi_inv","lulc_w"]]
                      .mean().reset_index())
        categories = ["LST Norm (w=0.40)","Pop Norm (w=0.30)",
                      "NDVI Inv (w=0.20)","LULC Weight (w=0.10)"]
        fig_comp = go.Figure()
        for _, row in components.iterrows():
            fig_comp.add_trace(go.Bar(
                name=row["risk_class"], x=categories,
                y=[row["lst_norm"], row["pop_norm"], row["ndvi_inv"], row["lulc_w"]],
                marker_color=risk_colors.get(row["risk_class"], "#94a3b8")
            ))
        fig_comp.update_layout(barmode="group", paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)", font_color="#e0e4f0",
            margin=dict(t=20, b=20))
        st.plotly_chart(fig_comp, use_container_width=True)

        st.markdown("---")

        st.markdown('<div class="section-header">📐 Pearson Correlation — HEI vs Variables</div>',
                    unsafe_allow_html=True)
        corr_df = pd.DataFrame({
            "Variable":  ["LULC Weight","NDVI Inverse","Population","LST"],
            "Pearson r": [0.6261, 0.6067, 0.5176, 0.0974],
            "Strength":  ["Moderate-Strong","Moderate-Strong","Moderate","Weak"]
        })
        fig_corr = px.bar(corr_df, x="Pearson r", y="Variable", orientation="h",
            color="Pearson r", color_continuous_scale="RdYlGn",
            text="Pearson r", title="Pearson Correlation Coefficients")
        fig_corr.update_traces(texttemplate="%{text:.4f}", textposition="outside")
        fig_corr.update_layout(paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)", font_color="#e0e4f0",
            xaxis=dict(range=[0, 0.75]), coloraxis_showscale=False,
            margin=dict(t=40, b=20))
        st.plotly_chart(fig_corr, use_container_width=True)

        urban_morph = load_urban_morphology()
        if not urban_morph.empty:
            st.markdown('<div class="section-header">🏗️ Urban Morphology Data</div>',
                        unsafe_allow_html=True)
            st.dataframe(urban_morph, use_container_width=True, height=300)
    else:
        st.info("No data to display. Adjust your filters in the sidebar.")

# ══════════════════════════════════════════════
#  TAB 4 — LST MONTHLY PROFILE
# ══════════════════════════════════════════════
with tab4:
    st.markdown('<div class="section-header">🌡️ Monthly Land Surface Temperature Profile 2025</div>',
                unsafe_allow_html=True)

    lst_data = load_lst_monthly()

    if not lst_data.empty:
        months_label = ["Jan","Feb","Mar","Apr","May","Jun",
                        "Jul","Aug","Sep","Oct","Nov","Dec"]
        if len(lst_data) == 12:
            lst_data["month_name"] = months_label
        else:
            lst_data["month_name"] = lst_data["month"].astype(str)

        fig_lst = go.Figure()
        fig_lst.add_trace(go.Scatter(
            x=lst_data["month_name"], y=lst_data["lst_mean"],
            mode="lines+markers", name="Mean LST",
            line=dict(color="#ff6b35", width=3), marker=dict(size=8)
        ))
        fig_lst.add_trace(go.Scatter(
            x=lst_data["month_name"], y=lst_data["lst_max"],
            mode="lines", name="Max LST",
            line=dict(color="#ef4444", dash="dash", width=2)
        ))
        fig_lst.add_trace(go.Scatter(
            x=lst_data["month_name"], y=lst_data["lst_min"],
            mode="lines", name="Min LST",
            line=dict(color="#3b82f6", dash="dot", width=2)
        ))
        fig_lst.add_trace(go.Scatter(
            x=lst_data["month_name"].tolist() + lst_data["month_name"].tolist()[::-1],
            y=lst_data["lst_max"].tolist() + lst_data["lst_min"].tolist()[::-1],
            fill="toself", fillcolor="rgba(255,107,53,0.1)",
            line=dict(color="rgba(255,255,255,0)"),
            name="Min-Max Band", showlegend=True
        ))
        if lst_data["lst_max"].max() > 40:
            fig_lst.add_hrect(
                y0=40, y1=float(lst_data["lst_max"].max()) + 1,
                fillcolor="red", opacity=0.06,
                annotation_text="Heat stress zone (>40°C)",
                annotation_position="top left"
            )
        fig_lst.update_layout(
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
            font_color="#e0e4f0", yaxis_title="Temperature (°C)",
            xaxis_title="Month", margin=dict(t=20, b=40),
            legend=dict(orientation="h", y=-0.25), height=440
        )
        st.plotly_chart(fig_lst, use_container_width=True)

        st.markdown('<div class="section-header">📊 LST Standard Deviation by Month</div>',
                    unsafe_allow_html=True)
        fig_std = px.bar(lst_data, x="month_name", y="lst_stddev",
            color="lst_stddev", color_continuous_scale="Reds",
            title="LST Variability (Std Dev) per Month")
        fig_std.update_layout(paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)", font_color="#e0e4f0",
            coloraxis_showscale=False, margin=dict(t=40, b=20))
        st.plotly_chart(fig_std, use_container_width=True)

        st.markdown('<div class="section-header">📋 Raw LST Monthly Data</div>',
                    unsafe_allow_html=True)
        st.dataframe(lst_data, use_container_width=True)
    else:
        st.warning("⚠️ lst_monthly.csv could not be loaded.")

# ══════════════════════════════════════════════
#  TAB 5 — DATA TABLE
# ══════════════════════════════════════════════
with tab5:
    st.markdown('<div class="section-header">📋 HEI Export — Full Data Table</div>',
                unsafe_allow_html=True)

    if not df.empty:
        table_cols = ["gid","hei_score","risk_class","risk_code",
                      "population","ndvi","lulc_class","urban_class",
                      "lst_norm","pop_norm","ndvi_inv","lulc_w",
                      "color_hex","latitude","longitude"]
        available_cols = [c for c in table_cols if c in df.columns]
        display_df = df[available_cols].copy()

        search = st.text_input("🔎 Search (Risk Class / LULC / Urban Class)", "")
        if search:
            mask = display_df.apply(
                lambda col: col.astype(str).str.contains(search, case=False)
            ).any(axis=1)
            display_df = display_df[mask]

        st.markdown(f"**Showing {len(display_df):,} rows**")
        st.dataframe(display_df, use_container_width=True, height=500)

        csv = display_df.to_csv(index=False).encode("utf-8")
        st.download_button("⬇️ Download Filtered Data as CSV",
            csv, "urban_heat_data.csv", "text/csv")
    else:
        st.info("No data. Adjust sidebar filters.")
