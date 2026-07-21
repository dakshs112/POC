import streamlit as st
import pandas as pd

from api import (
    get_posts,
    get_stats,
    get_authors,
    get_timeline,
    sync_posts
)

from charts import (
    authors_chart,
    timeline_chart
)

st.set_page_config(
    page_title="Reddit RSS Dashboard",
    page_icon="🏎️",
    layout="wide"
)

st.title("🏎️ Reddit RSS Analytics Dashboard")

# ==========================
# Sync Button
# ==========================

if st.button("🔄 Sync RSS Feed"):

    with st.spinner("Syncing latest posts..."):

        result = sync_posts()

    st.success("RSS feed synchronized!")

    st.write(result)

    st.rerun()

# ==========================
# Fetch Data
# ==========================

stats = get_stats()
posts = get_posts(limit=20)
authors = get_authors()
timeline = get_timeline()

posts_df = pd.DataFrame(posts)

# ==========================
# Metrics
# ==========================

st.subheader("Overview")

col1, col2, col3 = st.columns(3)

with col1:
    st.metric(
        "Total Posts",
        stats["total_posts"]
    )

with col2:
    st.metric(
        "Unique Authors",
        stats["unique_authors"]
    )

with col3:
    st.metric(
        "Last Updated",
        str(stats["last_updated"])[:19]
    )

# ==========================
# Charts
# ==========================

st.divider()

left, right = st.columns(2)

with left:

    st.plotly_chart(
        timeline_chart(timeline),
        use_container_width=True
    )

with right:

    st.plotly_chart(
        authors_chart(authors),
        use_container_width=True
    )

# ==========================
# Search
# ==========================

st.divider()

search = st.text_input(
    "🔍 Search Posts"
)

if search:

    posts_df = posts_df[
        posts_df["title"].str.contains(
            search,
            case=False,
            na=False
        )
    ]

# ==========================
# Posts Table
# ==========================

st.subheader("Latest Reddit Posts")

st.dataframe(
    posts_df,
    use_container_width=True
)