import pandas as pd
import plotly.express as px


def authors_chart(authors):

    df = pd.DataFrame(authors)

    fig = px.bar(
        df,
        x="_id",
        y="posts",
        title="Top Authors"
    )

    return fig


def timeline_chart(timeline):

    df = pd.DataFrame(timeline)

    fig = px.line(
        df,
        x="_id",
        y="count",
        markers=True,
        title="Posts Timeline"
    )

    return fig