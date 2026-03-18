import streamlit as st
import pandas as pd
import plotly.express as px
import gspread
from oauth2client.service_account import ServiceAccountCredentials

st.title("📊 Social Performance Dashboard")


@st.cache_data
def load_data():
    scope = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/drive",
    ]

    creds_dict = dict(st.secrets["gcp_service_account"])
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    client = gspread.authorize(creds)

    workbook = client.open("CLEAN DATA")

    ig_sheet = workbook.worksheet("instagram")
    tt_sheet = workbook.worksheet("tiktok")

    df_ig = pd.DataFrame(ig_sheet.get_all_records())
    df_tt = pd.DataFrame(tt_sheet.get_all_records())

    return df_ig, df_tt


def clean_instagram_data(df):
    df["date"] = pd.to_datetime(
        df["date"],
        format="%d/%m/%Y",
        errors="coerce"
    )
    df = df.dropna(subset=["date"])

    count_cols = [
        "views",
        "likes",
        "repost",
        "comments",
        "share",
        "saves",
        "all_interactions",
        "avg_watch_time",
        "sessions",
    ]

    percent_cols = [
        "views_from_followers",
        "views_non_followers",
        "engagement_rate",
        "int_from_followers",
        "int_from_nonfollowers",
        "percentage_of_videowatched",
        "percentage_of_viewerswhowatchedmorethan3s",
        "percentage_of_youthviewers",
        "clickthrough_rate",
    ]

    for col in count_cols:
        if col in df.columns:
            df[col] = (
                df[col]
                .astype(str)
                .str.replace(",", "", regex=False)
                .str.strip()
            )
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

    for col in percent_cols:
        if col in df.columns:
            df[col] = (
                df[col]
                .astype(str)
                .str.replace("%", "", regex=False)
                .str.replace(",", "", regex=False)
                .str.strip()
            )
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

    return df


def clean_tiktok_data(df):
    df["date"] = pd.to_datetime(
        df["date"],
        format="%d/%m/%Y",
        errors="coerce"
    )
    df = df.dropna(subset=["date"])

    count_cols = [
        "views",
        "likes",
        "comments",
        "share",
        "saves",
        "all_interactions",
        "video_length",
        "avg_watch_time",
    ]

    percent_cols = [
        "engagement_rate",
        "percentage_of_videowatched",
        "percentage_of_youthviewers",
    ]

    for col in count_cols:
        if col in df.columns:
            df[col] = (
                df[col]
                .astype(str)
                .str.replace(",", "", regex=False)
                .str.strip()
            )
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

    for col in percent_cols:
        if col in df.columns:
            df[col] = (
                df[col]
                .astype(str)
                .str.replace("%", "", regex=False)
                .str.replace(",", "", regex=False)
                .str.strip()
            )
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

    return df


df_ig, df_tt = load_data()

df_ig = clean_instagram_data(df_ig)
df_tt = clean_tiktok_data(df_tt)

tab1, tab2 = st.tabs(["Instagram", "TikTok"])

with tab1:
    st.header("Instagram")

    total_views = df_ig["views"].sum()
    total_interactions = df_ig["all_interactions"].sum()
    avg_engagement_rate = df_ig["engagement_rate"].mean()

    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric("Total Views", f"{int(total_views):,}")

    with col2:
        st.metric("Total Interactions", f"{int(total_interactions):,}")

    with col3:
        st.metric("Avg Engagement Rate", f"{avg_engagement_rate:.2f}%")

    monthly_views = df_ig.set_index("date").resample("M")["views"].sum().reset_index()

    fig = px.bar(monthly_views, x="date", y="views", title="Instagram Views by Month")
    st.plotly_chart(fig, use_container_width=True)

    top_posts = df_ig.sort_values(by="views", ascending=False).head(5)

    st.subheader("Top 5 Instagram Posts by Views")
    st.dataframe(
        top_posts[
            [
                "date",
                "format",
                "post_or_story",
                "views",
                "all_interactions",
                "engagement_rate",
                "link",
            ]
        ],
        use_container_width=True
    )

with tab2:
    st.header("TikTok")

    total_views = df_tt["views"].sum()
    total_interactions = df_tt["all_interactions"].sum()
    avg_engagement_rate = df_tt["engagement_rate"].mean()

    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric("Total Views", f"{int(total_views):,}")

    with col2:
        st.metric("Total Interactions", f"{int(total_interactions):,}")

    with col3:
        st.metric("Avg Engagement Rate", f"{avg_engagement_rate:.2f}%")

    monthly_views = df_tt.set_index("date").resample("M")["views"].sum().reset_index()

    fig = px.bar(monthly_views, x="date", y="views", title="TikTok Views by Month")
    st.plotly_chart(fig, use_container_width=True)

    top_posts = df_tt.sort_values(by="views", ascending=False).head(5)

    st.subheader("Top 5 TikTok Posts by Views")
    st.dataframe(
        top_posts[
            [
                "date",
                "format",
                "post_or_story",
                "views",
                "all_interactions",
                "engagement_rate",
                "link",
            ]
        ],
        use_container_width=True
    )