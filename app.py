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
    df_ig_display = df_ig_filtered.copy()
    df_ig_display["save_share_rate"] = (
        (df_ig_display["saves"] + df_ig_display["share"])
        .div(df_ig_display["views"].replace(0, pd.NA))
        .mul(100)
        .fillna(0)
    )

    pg_posted_raw = df_ig_display["pg_posted"].astype(str).str.strip().str.lower()
    df_ig_display["pg_posted_flag"] = pg_posted_raw.map(
        {
            "true": True,
            "false": False,
            "yes": True,
            "no": False,
            "1": True,
            "0": False,
        }
    )
    df_ig_display["content_source"] = df_ig_display["pg_posted_flag"].map(
        {
            True: "PG Posted",
            False: "Influencer",
        }
    ).fillna("Unknown")

    influencer_df = df_ig_display[df_ig_display["pg_posted_flag"] == False]
    listing_df = df_ig_display[
        df_ig_display["campaign"].astype(str).str.strip().str.lower() == "listing"
    ]

    def format_delta(value, target):
        if pd.isna(value):
            return None
        return f"{value - target:+.2f} pts"

    def format_percent(value):
        if pd.isna(value):
            return "N/A"
        return f"{value:.2f}%"

    def format_number(value):
        if pd.isna(value):
            return "N/A"
        return f"{int(value):,}"

    st.subheader("Key Results")
    kr_cols = st.columns(5)

    median_save_share_rate = df_ig_display["save_share_rate"].median()
    median_engagement_rate = df_ig_display["engagement_rate"].median()
    median_video_views = df_ig_display["views"].median()
    median_youth_viewership = df_ig_display["percentage_of_youthviewers"].median()
    median_influencer_youth = influencer_df["percentage_of_youthviewers"].median()

    with kr_cols[0]:
        st.metric(
            "Median Save + Share Rate",
            format_percent(median_save_share_rate),
            delta=format_delta(median_save_share_rate, 2.0),
        )
    with kr_cols[1]:
        st.metric(
            "Median Engagement Rate",
            format_percent(median_engagement_rate),
            delta=format_delta(median_engagement_rate, 1.8),
        )
    with kr_cols[2]:
        st.metric(
            "IG Median Video Views",
            format_number(median_video_views),
            delta=None if pd.isna(median_video_views) else f"{int(median_video_views - 10000):+,}",
        )
    with kr_cols[3]:
        st.metric(
            "Median Youth Viewership %",
            format_percent(median_youth_viewership),
            delta=format_delta(median_youth_viewership, 15.0),
        )
    with kr_cols[4]:
        st.metric(
            "Median Influencer Youth %",
            format_percent(median_influencer_youth),
            delta=format_delta(median_influencer_youth, 25.0),
        )

    st.subheader("Diagnostics")

    monthly_views = (
        df_ig_display.set_index("date").resample("M")["views"].sum().reset_index()
    )
    monthly_views["month_label"] = monthly_views["date"].dt.strftime("%b %Y")
    fig_monthly_views = px.line(
        monthly_views,
        x="date",
        y="views",
        markers=True,
        title="Monthly Views Trend",
    )
    fig_monthly_views.update_layout(xaxis_title="", yaxis_title="Views")

    campaign_metrics = (
        df_ig_display.groupby("campaign", dropna=False)
        .agg(
            median_engagement_rate=("engagement_rate", "median"),
            median_save_share_rate=("save_share_rate", "median"),
        )
        .reset_index()
    )
    campaign_metrics["campaign"] = campaign_metrics["campaign"].fillna("Unknown")
    campaign_metrics = campaign_metrics.sort_values("campaign")

    fig_campaign_engagement = px.bar(
        campaign_metrics,
        x="campaign",
        y="median_engagement_rate",
        title="Median Engagement Rate by Campaign",
    )
    fig_campaign_engagement.update_layout(xaxis_title="", yaxis_title="Median Engagement Rate (%)")

    fig_campaign_save_share = px.bar(
        campaign_metrics,
        x="campaign",
        y="median_save_share_rate",
        title="Median Save + Share Rate by Campaign",
    )
    fig_campaign_save_share.update_layout(xaxis_title="", yaxis_title="Median Save + Share Rate (%)")

    youth_source = (
        df_ig_display[df_ig_display["content_source"] != "Unknown"]
        .groupby("content_source")
        .agg(median_youth_viewership=("percentage_of_youthviewers", "median"))
        .reset_index()
    )
    fig_youth_source = px.bar(
        youth_source,
        x="content_source",
        y="median_youth_viewership",
        title="Youth Viewership: PG Posted vs Influencer",
    )
    fig_youth_source.update_layout(xaxis_title="", yaxis_title="Median Youth Viewership (%)")

    top_youth_posts = df_ig_display.sort_values(
        by="percentage_of_youthviewers",
        ascending=False,
    ).head(5)
    top_youth_posts["post_label"] = top_youth_posts["date"].dt.strftime("%d %b %Y")
    fig_top_youth_posts = px.bar(
        top_youth_posts.sort_values("percentage_of_youthviewers"),
        x="percentage_of_youthviewers",
        y="post_label",
        orientation="h",
        hover_data=["campaign", "views", "engagement_rate", "save_share_rate", "link"],
        title="Top 5 Posts by Youth Viewership",
    )
    fig_top_youth_posts.update_layout(xaxis_title="Youth Viewership (%)", yaxis_title="")

    diag_col1, diag_col2 = st.columns(2)
    with diag_col1:
        st.plotly_chart(fig_monthly_views, use_container_width=True)
        st.plotly_chart(fig_campaign_save_share, use_container_width=True)
        st.plotly_chart(fig_top_youth_posts, use_container_width=True)
    with diag_col2:
        st.plotly_chart(fig_campaign_engagement, use_container_width=True)
        st.plotly_chart(fig_youth_source, use_container_width=True)

    st.subheader('Campaign Deep Dive: "listing"')

    deep_dive_col1, deep_dive_col2 = st.columns([1, 2])
    with deep_dive_col1:
        st.markdown("**Listing Summary**")
        st.metric("Median Views", format_number(listing_df["views"].median()))
        st.metric(
            "Median Save + Share Rate",
            format_percent(listing_df["save_share_rate"].median()),
        )
        st.metric(
            "Median Youth Viewership",
            format_percent(listing_df["percentage_of_youthviewers"].median()),
        )

    with deep_dive_col2:
        listing_table = listing_df[
            [
                "date",
                "views",
                "engagement_rate",
                "save_share_rate",
                "percentage_of_youthviewers",
                "link",
            ]
        ].sort_values("date", ascending=False)
        if listing_table.empty:
            st.info('No "listing" campaign posts are available for the current Instagram date filter.')
        else:
            st.dataframe(listing_table, use_container_width=True)

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
