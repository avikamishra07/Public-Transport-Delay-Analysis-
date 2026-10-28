import altair as alt
import pandas as pd
import streamlit as st
from cassandra.cluster import Cluster

st.set_page_config(
    page_title="Public Transport Delay Analysis",
    page_icon="🚆",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# ---------------------------------------------------------------------------
# Design tokens
# Signage-style type (Barlow, the face used on rail and road signs), deep navy
# ink, one teal for data, and a signal red reserved for delays.
# ---------------------------------------------------------------------------
NIGHT = "#0B1A2F"      # deep navy: header, text
HARBOUR = "#1B3A5C"    # secondary navy
TEAL = "#0F8B8D"       # primary data colour
TEAL_SOFT = "#CFE5E6"
SIGNAL = "#D62839"     # delays only
MIST = "#EDF1F4"       # page background
WHITE = "#FFFFFF"
RULE = "#D3DCE3"
MUTED = "#566879"
FONT = "Barlow, 'Segoe UI', sans-serif"
CHART_FONT = "Barlow, Segoe UI, Arial, sans-serif"
CHART_FONT_NUM = "Barlow Condensed, Barlow, Segoe UI, Arial, sans-serif"

CSS = f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Barlow:wght@400;500;600;700&family=Barlow+Condensed:wght@500;600;700&display=swap');

html, body, [class*="css"], .stApp {{ font-family: {FONT}; color: {NIGHT}; }}
.stApp {{ background: {MIST}; }}
header[data-testid="stHeader"] {{ background: transparent; }}
#MainMenu, footer, .stAppDeployButton, [data-testid="stAppDeployButton"] {{ visibility: hidden; }}
.block-container {{ padding: 1.5rem 1.5rem 3rem; max-width: 1240px; }}

/* No sidebar: everything lives on one page */
section[data-testid="stSidebar"],
div[data-testid="stSidebarCollapsedControl"],
div[data-testid="collapsedControl"] {{ display: none !important; }}

/* ---------- Masthead ---------- */
.masthead {{
    background: {NIGHT}; color: #fff; border-radius: 6px;
    padding: 2.4rem 2.4rem 2.2rem; box-shadow: inset 0 -5px 0 {TEAL};
}}
.masthead h1 {{
    font-family: 'Barlow Condensed', {FONT}; font-weight: 600; color: #fff;
    font-size: clamp(2.1rem, 5vw, 3.4rem); line-height: 1.05;
    letter-spacing: .005em; margin: 0; padding: 0;
}}
.masthead p {{
    color: #A9BDD1; font-size: 1.05rem; line-height: 1.5;
    margin: .7rem 0 0; max-width: 46rem;
}}

/* ---------- Overview: figures + the train ---------- */
.overview {{
    display: grid; grid-template-columns: 1.25fr 1fr 1fr; gap: 0;
    margin: 2.2rem 0 1.6rem;
}}
.fig {{ padding: 0 2rem; border-left: 1px solid {RULE}; }}
.fig:first-child {{ padding-left: 0; border-left: none; }}
.fig-label {{ color: {MUTED}; font-size: 1rem; font-weight: 500; margin-bottom: .1rem; }}
.fig-num {{
    font-family: 'Barlow Condensed', {FONT}; font-weight: 600; color: {NIGHT};
    font-size: clamp(2.4rem, 4.6vw, 3.6rem); line-height: 1.05;
    font-variant-numeric: tabular-nums;
}}
.fig-num.rate {{ color: {SIGNAL}; font-size: clamp(3.2rem, 7vw, 5.6rem); }}
.fig-num.rate small {{ font-size: .5em; margin-left: .08em; }}

.train {{ display: flex; gap: 2px; height: 30px; }}
.coach {{ flex: 1; border-radius: 2px; background: {TEAL}; }}
.coach.late {{ background: {SIGNAL}; }}
.coach:first-child {{ border-radius: 12px 2px 2px 12px; }}
.rail {{
    height: 7px; margin-top: 5px;
    background:
        repeating-linear-gradient(90deg, {HARBOUR} 0 3px, transparent 3px 14px) 0 0 / 100% 7px no-repeat,
        linear-gradient({HARBOUR}, {HARBOUR}) 0 3px / 100% 1px no-repeat;
    opacity: .55;
}}
.legend {{ display: flex; flex-wrap: wrap; gap: .4rem 1.6rem; margin-top: .8rem; font-size: .95rem; font-weight: 500; }}
.key::before {{
    content: ""; display: inline-block; width: 14px; height: 14px; border-radius: 3px;
    background: {TEAL}; margin-right: .5rem; vertical-align: -2px;
}}
.key.late::before {{ background: {SIGNAL}; }}
.train-note {{ color: {MUTED}; font-size: .9rem; margin: .4rem 0 0; }}

/* ---------- Route navigation (tabs as stations) ---------- */
[role="tablist"] {{
    position: relative; display: flex; gap: 0; background: transparent;
    border: none; padding: 1.2rem 0 .4rem; margin-top: 1.4rem;
}}
[role="tablist"]::before {{
    content: ""; position: absolute; left: 12.5%; right: 12.5%;
    top: calc(1.2rem + 9px); height: 3px; background: {RULE};
}}
[role="tab"] {{
    flex: 1 1 0; height: auto; background: transparent; border: none;
    display: flex; flex-direction: column; align-items: center; gap: .6rem;
    min-width: 0; padding: 0 .2rem .5rem; position: relative; color: {MUTED};
    font-size: 1.05rem; font-weight: 600;
}}
[role="tab"] p {{ font-size: 1.05rem; font-weight: 600; color: inherit; }}
[role="tab"]::before {{
    content: ""; width: 19px; height: 19px; box-sizing: border-box; border-radius: 50%;
    background: {MIST}; border: 3px solid {HARBOUR}; position: relative; z-index: 1;
}}
[role="tab"]:hover {{ color: {NIGHT}; background: transparent; }}
[role="tab"][aria-selected="true"] {{ color: {NIGHT}; }}
[role="tab"][aria-selected="true"]::before {{
    background: {TEAL}; border-color: {TEAL}; box-shadow: 0 0 0 5px rgba(15, 139, 141, .22);
}}
[role="tab"]:focus-visible {{ outline: 2px solid {TEAL}; outline-offset: 2px; }}
[data-baseweb="tab-highlight"], [data-baseweb="tab-border"], .react-aria-SelectionIndicator {{ display: none !important; }}

/* ---------- Section sheet ---------- */
.sec-title {{
    font-family: 'Barlow Condensed', {FONT}; font-weight: 600; font-size: 2.1rem;
    line-height: 1.1; margin: 1.2rem 0 .9rem; color: {NIGHT}; padding: 0;
}}
div[data-testid="stVerticalBlockBorderWrapper"]:has(.sheet) {{
    background: {WHITE}; border: 1px solid {RULE}; border-radius: 6px; padding: 1.2rem 1.4rem 1.4rem;
}}
.block-title {{
    font-size: 1.15rem; font-weight: 600; color: {NIGHT}; margin: 0 0 .1rem;
}}
.block-note {{ color: {MUTED}; font-size: .95rem; margin: 0 0 1rem; }}
.block-gap {{ height: 1.6rem; border-bottom: 1px solid {RULE}; margin-bottom: 1.4rem; }}
div[data-testid="stDataFrame"] {{ border: 1px solid {RULE}; border-radius: 4px; overflow: hidden; }}

/* ---------- Footer ---------- */
.footer {{
    display: flex; justify-content: space-between; flex-wrap: wrap; gap: .4rem 2rem;
    margin-top: 2.4rem; padding-top: 1rem; border-top: 3px solid {NIGHT};
    color: {MUTED}; font-size: .92rem;
}}
.footer b {{ color: {NIGHT}; font-weight: 600; }}

@media (max-width: 800px) {{
    .masthead {{ padding: 1.6rem 1.3rem 1.5rem; }}
    .overview {{ grid-template-columns: 1fr; gap: 1.1rem; }}
    .fig {{ padding: 0; border-left: none; }}
    .coach {{ border-radius: 1px; }}
    .train {{ gap: 1px; }}
    [role="tab"], [role="tab"] p {{ font-size: .8rem; line-height: 1.2; text-align: center; }}
    [role="tablist"] {{ overflow: hidden; }}
    .sec-title {{ font-size: 1.7rem; }}
}}
</style>
"""
st.markdown(CSS, unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Chart styling (same data, same chart types, same sort order as before)
# ---------------------------------------------------------------------------
def finish(chart):
    return (
        chart.configure(background="transparent")
        .configure_view(stroke=None)
        .configure_axis(
            labelFont=CHART_FONT, titleFont=CHART_FONT, labelColor=MUTED, titleColor=MUTED,
            labelFontSize=12, titleFontSize=12, titleFontWeight=500,
            gridColor="#E4EAEF", domainColor=RULE, tickColor=RULE
        )
    )


def bar_chart(data, value, value_title, fmt=".2f"):
    """Horizontal bars in the order of the (already sorted) dataframe."""
    order = data["category_name"].tolist()
    top = float(data[value].max()) if len(data) else 0.0

    base = alt.Chart(data).encode(
        y=alt.Y(
            "category_name:N", sort=order, title=None,
            axis=alt.Axis(
                ticks=False, domain=False, labelLimit=260, labelPadding=8,
                labelColor=NIGHT, labelFontSize=13
            )
        ),
        x=alt.X(
            f"{value}:Q", title=value_title,
            scale=alt.Scale(domain=[0, top * 1.18 if top > 0 else 1])
        ),
        tooltip=[
            alt.Tooltip("category_name:N", title="Name"),
            alt.Tooltip(f"{value}:Q", title=value_title, format=fmt),
        ],
    )
    bars = base.mark_bar(size=14, cornerRadiusEnd=2, color=TEAL)
    labels = base.mark_text(
        align="left", dx=6, font=CHART_FONT_NUM, fontSize=15, fontWeight=600, color=NIGHT
    ).encode(text=alt.Text(f"{value}:Q", format=fmt))

    chart = alt.layer(bars, labels).properties(width="container", height=alt.Step(28))
    return finish(chart)


def line_chart(data, value, value_title, x_title):
    order = data["category_name"].tolist()

    base = alt.Chart(data).encode(
        x=alt.X(
            "category_name:N", sort=order, title=x_title,
            axis=alt.Axis(labelAngle=0, labelOverlap=True, ticks=False, grid=False, labelPadding=8)
        ),
        y=alt.Y(f"{value}:Q", title=value_title, scale=alt.Scale(zero=False, nice=True)),
        tooltip=[
            alt.Tooltip("category_name:N", title=x_title),
            alt.Tooltip(f"{value}:Q", title=value_title, format=".2f"),
        ],
    )
    line = base.mark_line(color=HARBOUR, strokeWidth=2.5)
    points = base.mark_point(filled=True, size=70, opacity=1, color=TEAL)
    chart = alt.layer(line, points).properties(width="container", height=380)
    return finish(chart)


def scatter_chart(data, x, y, x_title, y_title):
    """One labelled point per row: volume on x, delay rate on y (both from zero)."""
    x_max = float(data[x].max()) if len(data) else 0.0
    y_max = float(data[y].max()) if len(data) else 0.0

    base = alt.Chart(data).encode(
        x=alt.X(
            f"{x}:Q", title=x_title,
            scale=alt.Scale(domain=[0, x_max * 1.15 if x_max > 0 else 1]),
            axis=alt.Axis(format=",.0f")
        ),
        y=alt.Y(
            f"{y}:Q", title=y_title,
            scale=alt.Scale(domain=[0, y_max * 1.15 if y_max > 0 else 1])
        ),
        tooltip=[
            alt.Tooltip("category_name:N", title="Name"),
            alt.Tooltip(f"{x}:Q", title=x_title, format=",.0f"),
            alt.Tooltip(f"{y}:Q", title=y_title, format=".2f"),
        ],
    )
    points = base.mark_point(filled=True, size=110, opacity=1, color=TEAL)
    names = base.mark_text(
        align="left", dx=9, font=CHART_FONT, fontSize=12, color=NIGHT
    ).encode(text="category_name:N")
    chart = alt.layer(points, names).properties(width="container", height=420)
    return finish(chart)


def column_chart(data, value, value_title, x_title):
    """Vertical bars in the order of the (already sorted) dataframe."""
    order = data["category_name"].tolist()
    chart = alt.Chart(data).mark_bar(color=TEAL, cornerRadiusEnd=2).encode(
        x=alt.X(
            "category_name:N", sort=order, title=x_title,
            axis=alt.Axis(labelAngle=0, labelOverlap=True, ticks=False, grid=False, labelPadding=8)
        ),
        y=alt.Y(f"{value}:Q", title=value_title, axis=alt.Axis(format=",.0f")),
        tooltip=[
            alt.Tooltip("category_name:N", title=x_title),
            alt.Tooltip(f"{value}:Q", title=value_title, format=",.0f"),
        ],
    ).properties(width="container", height=280)
    return finish(chart)


# ---------------------------------------------------------------------------
# UI helpers
# ---------------------------------------------------------------------------
def block_header(title, note):
    st.markdown(f'<div class="block-title">{title}</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="block-note">{note}</div>', unsafe_allow_html=True)


def block_divider():
    st.markdown('<div class="block-gap"></div>', unsafe_allow_html=True)


def section_title(title):
    st.markdown(f'<h2 class="sec-title">{title}</h2>', unsafe_allow_html=True)


def show_chart(chart):
    st.altair_chart(chart, use_container_width=True, theme=None)


# Display-only column labels for the tables (data is unchanged).
COLUMN_LABELS = {
    "category": "Category",
    "category_name": "Name",
    "total_journeys": st.column_config.NumberColumn("Total Journeys", format="%d"),
    "delayed_journeys": st.column_config.NumberColumn("Delayed Journeys", format="%d"),
    "delay_rate": st.column_config.NumberColumn("Delay Rate (%)", format="%.2f"),
    "avg_delay_all": st.column_config.NumberColumn("Avg Delay (All)", format="%.2f"),
    "avg_delay_when_delayed": st.column_config.NumberColumn(
        "Avg Delay (When Delayed)", format="%.2f"
    ),
}

SECTIONS = ["Railway Zones", "Train Types", "Departure Hours", "Delay Causes"]


# ---------------------------------------------------------------------------
# Masthead
# ---------------------------------------------------------------------------
st.markdown(
    """
    <div class="masthead">
        <h1>Public Transport Delay Analysis</h1>
        <p>Which railway zones, train types and departure hours run late, and what
        causes the delays. Big Data analytics on Hadoop MapReduce output stored in Cassandra.</p>
    </div>
    """,
    unsafe_allow_html=True
)


# ---------------------------------------------------------------------------
# Data access (unchanged)
# ---------------------------------------------------------------------------
@st.cache_resource
def connect_cassandra():
    cluster = Cluster(["127.0.0.1"], port=9042)
    session = cluster.connect("transport_analysis")
    return cluster, session


@st.cache_data(ttl=60)
def load_data():
    cluster, session = connect_cassandra()
    rows = session.execute("SELECT * FROM delay_summary")
    data = [row._asdict() for row in rows]
    return pd.DataFrame(data)


try:
    df = load_data()

    if df.empty:
        st.warning("No summary data found in Cassandra.")
        st.stop()

    df.columns = [column.lower() for column in df.columns]
    df["category"] = df["category"].str.strip()
    df["category_name"] = df["category_name"].str.strip()

    # Calculate overall journey statistics.
    total = int(df["total_journeys"].sum())
    delayed = int(df["delayed_journeys"].sum())

    total_journeys = total // 4
    delayed_journeys = delayed // 4
    delay_rate = (
        delayed_journeys / total_journeys * 100
        if total_journeys else 0
    )

    # ----- Overview: three figures and one train of 100 coaches -----
    late_coaches = max(0, min(100, round(delay_rate)))
    coaches = (
        '<span class="coach late"></span>' * late_coaches
        + '<span class="coach"></span>' * (100 - late_coaches)
    )
    st.markdown(
        f"""
        <div class="overview">
            <div class="fig">
                <div class="fig-label">Overall Delay Rate</div>
                <div class="fig-num rate">{delay_rate:.2f}<small>%</small></div>
            </div>
            <div class="fig">
                <div class="fig-label">Total Journeys</div>
                <div class="fig-num">{total_journeys:,}</div>
            </div>
            <div class="fig">
                <div class="fig-label">Delayed Journeys</div>
                <div class="fig-num">{delayed_journeys:,}</div>
            </div>
        </div>
        <div class="train" role="img"
             aria-label="{late_coaches} of every 100 journeys were delayed">{coaches}</div>
        <div class="rail"></div>
        <div class="legend">
            <span class="key late">Delayed ({late_coaches} of 100)</span>
            <span class="key">Not delayed ({100 - late_coaches} of 100)</span>
        </div>
        <p class="train-note">Each coach is 1 in 100 journeys, using the overall delay rate
        rounded to a whole number. Source: Cassandra table
        transport_analysis.delay_summary, {len(df):,} summary rows.</p>
        """,
        unsafe_allow_html=True
    )

    zones = df[df["category"] == "ZONE"].copy()
    trains = df[df["category"] == "TRAIN_TYPE"].copy()
    hours = df[df["category"] == "DEPARTURE_HOUR"].copy()
    causes = df[
        (df["category"] == "DELAY_CAUSE") &
        (df["category_name"].str.lower() != "on time")
    ].copy()

    # ----- Sections, navigated along the route -----
    tab1, tab2, tab3, tab4 = st.tabs(SECTIONS)

    with tab1:
        section_title("Railway Zones")
        with st.container(border=True):
            st.markdown('<span class="sheet"></span>', unsafe_allow_html=True)
            block_header(
                "Delay Rate by Railway Zone",
                "Percentage of journeys marked as delayed in each zone."
            )
            zones = zones.sort_values("delay_rate", ascending=False)
            show_chart(bar_chart(zones, "delay_rate", "Delay rate (%)"))
            block_divider()
            block_header("Zone data", "Detailed figures for each railway zone.")
            st.dataframe(
                zones, use_container_width=True, hide_index=True,
                column_config=COLUMN_LABELS
            )

    with tab2:
        section_title("Train Types")
        with st.container(border=True):
            st.markdown('<span class="sheet"></span>', unsafe_allow_html=True)
            block_header(
                "Delay Rate by Train Type",
                "Compare the percentage of delayed journeys across train types."
            )
            trains = trains.sort_values("delay_rate", ascending=False)
            show_chart(bar_chart(trains, "delay_rate", "Delay rate (%)"))
            block_divider()
            block_header("Train type data", "Detailed figures for each train type.")
            st.dataframe(
                trains, use_container_width=True, hide_index=True,
                column_config=COLUMN_LABELS
            )

    with tab3:
        section_title("Departure Hours")
        with st.container(border=True):
            st.markdown('<span class="sheet"></span>', unsafe_allow_html=True)
            block_header(
                "Delay Rate by Departure Hour",
                "Explore how delay rates vary throughout the day."
            )
            hours = hours.sort_values("category_name")
            show_chart(line_chart(hours, "delay_rate", "Delay rate (%)", "Departure hour"))
            block_divider()
            block_header(
                "Journeys by Departure Hour",
                "Number of journeys leaving in each hour, to read the delay rate against traffic."
            )
            show_chart(column_chart(hours, "total_journeys", "Total journeys", "Departure hour"))
            block_divider()
            block_header("Departure hour data", "Detailed figures for each departure hour.")
            st.dataframe(
                hours, use_container_width=True, hide_index=True,
                column_config=COLUMN_LABELS
            )

    with tab4:
        section_title("Delay Causes")
        with st.container(border=True):
            st.markdown('<span class="sheet"></span>', unsafe_allow_html=True)
            block_header(
                "Average Delay by Reported Cause",
                "Average delay in minutes for journeys with each reported cause."
            )
            causes = causes.sort_values(
                "avg_delay_when_delayed",
                ascending=False
            )
            show_chart(bar_chart(causes, "avg_delay_when_delayed", "Average delay (minutes)"))
            block_divider()
            block_header(
                "Delayed Journeys by Reported Cause",
                "How many delayed journeys each cause accounts for."
            )
            causes_by_count = causes.sort_values("delayed_journeys", ascending=False)
            show_chart(bar_chart(
                causes_by_count, "delayed_journeys", "Delayed journeys", fmt=",.0f"
            ))
            block_divider()
            block_header("Delay cause data", "Detailed figures for each reported cause.")
            st.dataframe(
                causes, use_container_width=True, hide_index=True,
                column_config=COLUMN_LABELS
            )

except Exception as e:
    st.error("Unable to load dashboard data.")
    st.code(str(e))
    st.info(
        "Check that Cassandra is running and listening on port 9042."
    )

# ---------------------------------------------------------------------------
# Footer
# ---------------------------------------------------------------------------
st.markdown(
    """
    <div class="footer">
        <span><b>Public Transport Delay Analysis</b>, a Big Data analytics project</span>
        <span>Processed with Hadoop MapReduce, stored in Apache Cassandra, shown with Streamlit</span>
    </div>
    """,
    unsafe_allow_html=True
)