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
    st.subheader("Filters")

    date_range = st.selectbox(
        "Select Date Range",
        ["All Time", "Last 30 Days", "Last 90 Days", "Custom Range"]
    )

    df_ig_filtered = df_ig.copy()

    if date_range == "Last 30 Days":
        cutoff = pd.Timestamp.today().normalize() - pd.Timedelta(days=30)
        df_ig_filtered = df_ig[df_ig["date"] >= cutoff]
    elif date_range == "Last 90 Days":
        cutoff = pd.Timestamp.today().normalize() - pd.Timedelta(days=90)
        df_ig_filtered = df_ig[df_ig["date"] >= cutoff]
    elif date_range == "Custom Range":
        min_date = df_ig["date"].min().date()
        max_date = df_ig["date"].max().date()
        custom_range = st.date_input(
            "Select Custom Date Range",
            value=(min_date, max_date),
            min_value=min_date,
            max_value=max_date,
        )

        if isinstance(custom_range, tuple) and len(custom_range) == 2:
            start_date, end_date = custom_range
        elif isinstance(custom_range, list) and len(custom_range) == 2:
            start_date, end_date = custom_range
        elif custom_range:
            start_date = custom_range
            end_date = max_date
        else:
            start_date, end_date = min_date, max_date

        start_ts = pd.Timestamp(start_date)
        end_ts = pd.Timestamp(end_date) + pd.Timedelta(days=1) - pd.Timedelta(microseconds=1)
        df_ig_filtered = df_ig[
            (df_ig["date"] >= start_ts) & (df_ig["date"] <= end_ts)
        ]

    st.header("Instagram")

    total_views = df_ig_filtered["views"].sum()
    total_interactions = df_ig_filtered["all_interactions"].sum()
    avg_engagement_rate = df_ig_filtered["engagement_rate"].mean()

    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric("Total Views", f"{int(total_views):,}")

    with col2:
        st.metric("Total Interactions", f"{int(total_interactions):,}")

    with col3:
        st.metric("Avg Engagement Rate", f"{avg_engagement_rate:.2f}%")

    monthly_views = (
        df_ig_filtered.set_index("date").resample("M")["views"].sum().reset_index()
    )

    fig = px.bar(monthly_views, x="date", y="views", title="Instagram Views by Month")
    st.plotly_chart(fig, use_container_width=True)

    top_posts = df_ig_filtered.sort_values(by="views", ascending=False).head(5)

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
