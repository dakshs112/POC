import streamlit as st
import pandas as pd

from api import (
    get_posts,
    get_stats,
    get_authors,
    get_timeline,
    sync_posts,
)

from charts import authors_chart, timeline_chart

# --------------------------------------------------
# Page Config
# --------------------------------------------------

st.set_page_config(
    page_title="Reddit RSS Dashboard",
    page_icon="🏎️",
    layout="wide",
)

# --------------------------------------------------
# Styling
# --------------------------------------------------

st.markdown(
    """
    <style>
    .stApp { background-color: #0E0E14; }

    .dashboard-header {
        display: flex;
        align-items: center;
        gap: 0.75rem;
        padding: 0.5rem 0 1.25rem 0;
    }
    .dashboard-header h1 {
        font-size: 2rem;
        margin: 0;
        background: linear-gradient(90deg, #E10600, #FF6B5B);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
    }
    .dashboard-subtitle {
        color: #9A9AA5;
        font-size: 0.95rem;
        margin-top: -0.5rem;
    }

    div[data-testid="stMetric"] {
        background-color: #1A1A23;
        border: 1px solid #2A2A35;
        border-left: 3px solid #E10600;
        border-radius: 10px;
        padding: 1rem 1.2rem;
    }
    div[data-testid="stMetricValue"] { color: #F5F5F5; }
    div[data-testid="stMetricLabel"] { color: #9A9AA5; }

    .stTabs [data-baseweb="tab-list"] { gap: 6px; }
    .stTabs [data-baseweb="tab"] {
        background-color: #1A1A23;
        border-radius: 8px 8px 0 0;
        padding: 0.5rem 1.1rem;
        color: #9A9AA5;
    }
    .stTabs [aria-selected="true"] {
        background-color: #E10600 !important;
        color: white !important;
    }

    div[data-testid="stDataFrame"] { border: 1px solid #2A2A35; border-radius: 8px; }
    </style>
    """,
    unsafe_allow_html=True,
)

# --------------------------------------------------
# Header
# --------------------------------------------------

st.markdown(
    """
    <div class="dashboard-header">
        <h1>🏎️ Reddit RSS Analytics Dashboard</h1>
    </div>
    <div class="dashboard-subtitle">Live post activity, author leaderboard, and posting trends</div>
    """,
    unsafe_allow_html=True,
)

# --------------------------------------------------
# Sync Button
# --------------------------------------------------

sync_col, _ = st.columns([1, 5])
with sync_col:
    if st.button("🔄 Sync RSS Feed", use_container_width=True):
        with st.spinner("Syncing latest posts..."):
            result = sync_posts()
        if isinstance(result, dict) and result.get("error"):
            st.error(f"Sync failed: {result['error']}")
        else:
            st.success("RSS feed updated successfully!")
            st.rerun()

st.write("")

# --------------------------------------------------
# Fetch Data
# --------------------------------------------------

stats = get_stats()
posts = get_posts(limit=20)
authors = get_authors()
timeline = get_timeline()

posts_df = pd.DataFrame(posts)
authors_df = pd.DataFrame(authors)
timeline_df = pd.DataFrame(timeline)

authors_fig = authors_chart(authors)
timeline_fig = timeline_chart(timeline)


# --------------------------------------------------
# Tabs
# --------------------------------------------------

tab1, tab2, tab3, tab4 = st.tabs(
    ["📊 Overview", "📋 Latest Posts", "👤 Authors", "📈 Timeline"]
)

# ==================================================
# OVERVIEW
# ==================================================

with tab1:
    col1, col2, col3 = st.columns(3)
    col1.metric("Total Posts", stats.get("total_posts", 0))
    col2.metric("Unique Authors", stats.get("unique_authors", 0))
    col3.metric("Last Updated", str(stats.get("last_updated", "—"))[:19])

    st.write("")

    left, right = st.columns(2)
    with left:
        st.plotly_chart(timeline_fig, use_container_width=True, key="overview_timeline")
    with right:
        st.plotly_chart(authors_fig, use_container_width=True, key="overview_authors")

# ==================================================
# POSTS
# ==================================================

with tab2:
    st.subheader("Latest Reddit Posts")

    search_col, count_col = st.columns([4, 1])
    with search_col:
        search = st.text_input("🔍 Search posts", key="search_posts", placeholder="Filter by title...")

    filtered_df = posts_df.copy()
    if search and "title" in filtered_df.columns:
        filtered_df = filtered_df[filtered_df["title"].str.contains(search, case=False, na=False)]

    with count_col:
        st.metric("Showing", len(filtered_df))

    if filtered_df.empty:
        st.info("No posts to show yet — try syncing the feed.")
    else:
        st.dataframe(filtered_df, use_container_width=True, hide_index=True)
        st.download_button(
            "⬇️ Download as CSV",
            data=filtered_df.to_csv(index=False).encode("utf-8"),
            file_name="reddit_posts.csv",
            mime="text/csv",
        )

# ==================================================
# AUTHORS
# ==================================================

with tab3:
    st.subheader("Top Authors")
    st.plotly_chart(authors_fig, use_container_width=True, key="authors_chart")
    st.divider()
    if authors_df.empty:
        st.info("No author data yet.")
    else:
        st.dataframe(authors_df, use_container_width=True, hide_index=True)

# ==================================================
# TIMELINE
# ==================================================

with tab4:
    st.subheader("Posts Timeline")
    st.plotly_chart(timeline_fig, use_container_width=True, key="timeline_chart")
    st.divider()
    if timeline_df.empty:
        st.info("No timeline data yet.")
    else:
        st.dataframe(timeline_df, use_container_width=True, hide_index=True)