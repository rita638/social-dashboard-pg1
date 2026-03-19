import streamlit as st
import pandas as pd
import plotly.express as px
import gspread
from oauth2client.service_account import ServiceAccountCredentials

st.title("📊 Social Performance Dashboard")


@st.cache_data(ttl=300)
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


def normalize_columns(df):
    df = df.copy()
    df.columns = (
        df.columns.astype(str)
        .str.strip()
        .str.lower()
        .str.replace(" ", "_", regex=False)
    )
    return df


def find_column(df, exact_name, contains_name=None):
    if exact_name in df.columns:
        return exact_name
    if contains_name is not None:
        for col in df.columns:
            if contains_name in col:
                return col
    return None


def clean_instagram_data(df):
    df = normalize_columns(df)
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
    df = normalize_columns(df)
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
    st.markdown(
        """
        <style>
        .kr-card {
            border: 1px solid #e5e7eb;
            border-left: 5px solid;
            border-radius: 12px;
            padding: 0.8rem 0.9rem;
            background: #ffffff;
            min-height: 132px;
        }
        .kr-label {
            font-size: 0.75rem;
            color: #6b7280;
            margin-bottom: 0.35rem;
        }
        .kr-value {
            font-size: 1.4rem;
            font-weight: 700;
            line-height: 1.1;
            margin-bottom: 0.35rem;
        }
        .kr-delta {
            font-size: 0.9rem;
            font-weight: 600;
            margin-bottom: 0.2rem;
        }
        .kr-status {
            font-size: 0.8rem;
            color: #4b5563;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

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

    def format_percent(value):
        if pd.isna(value):
            return "N/A"
        return f"{value:.2f}%"

    def format_number(value):
        if pd.isna(value):
            return "N/A"
        return f"{int(value):,}"

    def format_views_delta(value, target):
        if pd.isna(value):
            return "N/A"
        return f"{int(value - target):+,} views"

    def format_percent_delta(value, target):
        if pd.isna(value):
            return "N/A"
        return f"{value - target:+.1f}%"

    def render_kr_card(title, value_text, delta_text, status, is_above):
        border_color = "#16a34a" if is_above else "#dc2626"
        delta_color = "#16a34a" if is_above else "#dc2626"
        st.markdown(
            f"""
            <div class="kr-card" style="border-left-color: {border_color};">
                <div class="kr-label">{title}</div>
                <div class="kr-value">{value_text}</div>
                <div class="kr-delta" style="color: {delta_color};">{delta_text}</div>
                <div class="kr-status">{status}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.subheader("Key Results")
    kr_cols = st.columns(5)

    median_save_share_rate = df_ig_display["save_share_rate"].median()
    median_engagement_rate = df_ig_display["engagement_rate"].median()
    median_video_views = df_ig_display["views"].median()
    median_youth_viewership = df_ig_display["percentage_of_youthviewers"].median()
    median_influencer_youth = influencer_df["percentage_of_youthviewers"].median()

    with kr_cols[0]:
        render_kr_card(
            "Median Save + Share Rate",
            format_percent(median_save_share_rate),
            format_percent_delta(median_save_share_rate, 2.0),
            "Above Target" if median_save_share_rate >= 2.0 else "Below Target",
            median_save_share_rate >= 2.0,
        )
    with kr_cols[1]:
        render_kr_card(
            "Median Engagement Rate",
            format_percent(median_engagement_rate),
            format_percent_delta(median_engagement_rate, 1.8),
            "Above Target" if median_engagement_rate >= 1.8 else "Below Target",
            median_engagement_rate >= 1.8,
        )
    with kr_cols[2]:
        render_kr_card(
            "IG Median Video Views",
            format_number(median_video_views),
            format_views_delta(median_video_views, 10000),
            "Above Target" if median_video_views >= 10000 else "Below Target",
            median_video_views >= 10000,
        )
    with kr_cols[3]:
        render_kr_card(
            "Median Youth Viewership %",
            format_percent(median_youth_viewership),
            format_percent_delta(median_youth_viewership, 15.0),
            "Above Target" if median_youth_viewership >= 15.0 else "Below Target",
            median_youth_viewership >= 15.0,
        )
    with kr_cols[4]:
        render_kr_card(
            "Median Influencer Youth Viewership %",
            format_percent(median_influencer_youth),
            format_percent_delta(median_influencer_youth, 25.0),
            "Above Target" if median_influencer_youth >= 25.0 else "Below Target",
            median_influencer_youth >= 25.0,
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
        campaign_metrics.sort_values("median_engagement_rate", ascending=False),
        x="campaign",
        y="median_engagement_rate",
        title="Median Engagement Rate by Campaign",
    )
    fig_campaign_engagement.update_layout(xaxis_title="", yaxis_title="Median Engagement Rate (%)")
    fig_campaign_engagement.add_hline(
        y=1.8,
        line_dash="dash",
        line_color="#dc2626",
        annotation_text="Target 1.8%",
        annotation_position="top left",
    )

    fig_campaign_save_share = px.bar(
        campaign_metrics.sort_values("median_save_share_rate", ascending=False),
        x="campaign",
        y="median_save_share_rate",
        title="Median Save + Share Rate by Campaign",
    )
    fig_campaign_save_share.update_layout(xaxis_title="", yaxis_title="Median Save + Share Rate (%)")
    fig_campaign_save_share.add_hline(
        y=2.0,
        line_dash="dash",
        line_color="#dc2626",
        annotation_text="Target 2.0%",
        annotation_position="top left",
    )

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
    fig_youth_source.add_hline(
        y=15.0,
        line_dash="dot",
        line_color="#6b7280",
        annotation_text="PG Target 15%",
        annotation_position="top left",
    )

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

    st.subheader("Performance Highlights")
    insight_campaigns = campaign_metrics.dropna(subset=["median_engagement_rate"])
    top_campaign = (
        insight_campaigns.sort_values("median_engagement_rate", ascending=False).head(1)
    )
    lowest_campaign = (
        insight_campaigns.sort_values("median_engagement_rate", ascending=True).head(1)
    )

    youth_trend = (
        df_ig_display.set_index("date")
        .resample("M")["percentage_of_youthviewers"]
        .median()
        .dropna()
    )
    youth_direction = "holding steady"
    if len(youth_trend) >= 2:
        if youth_trend.iloc[-1] > youth_trend.iloc[0]:
            youth_direction = "improving"
        elif youth_trend.iloc[-1] < youth_trend.iloc[0]:
            youth_direction = "declining"

    source_engagement = (
        df_ig_display[df_ig_display["content_source"] != "Unknown"]
        .groupby("content_source")["engagement_rate"]
        .median()
    )
    influencer_vs_pg = "split is unavailable in the current filter"
    if {"Influencer", "PG Posted"}.issubset(source_engagement.index):
        if source_engagement["Influencer"] > source_engagement["PG Posted"]:
            influencer_vs_pg = (
                f"influencer content is outperforming PG posts on engagement "
                f"({source_engagement['Influencer']:.2f}% vs {source_engagement['PG Posted']:.2f}%)"
            )
        elif source_engagement["Influencer"] < source_engagement["PG Posted"]:
            influencer_vs_pg = (
                f"PG-posted content is outperforming influencer content on engagement "
                f"({source_engagement['PG Posted']:.2f}% vs {source_engagement['Influencer']:.2f}%)"
            )
        else:
            influencer_vs_pg = (
                f"influencer and PG-posted content are tied on engagement "
                f"at {source_engagement['Influencer']:.2f}%"
            )

    insights = []
    if not top_campaign.empty:
        insights.append(
            f"- Top campaign by median engagement is **{top_campaign.iloc[0]['campaign']}** at **{top_campaign.iloc[0]['median_engagement_rate']:.2f}%**."
        )
    if not lowest_campaign.empty:
        insights.append(
            f"- Lowest campaign by median engagement is **{lowest_campaign.iloc[0]['campaign']}** at **{lowest_campaign.iloc[0]['median_engagement_rate']:.2f}%**."
        )
    if len(youth_trend) >= 2:
        insights.append(
            f"- Youth viewership is **{youth_direction}**, moving from **{youth_trend.iloc[0]:.2f}%** to **{youth_trend.iloc[-1]:.2f}%** across the filtered period."
        )
    else:
        insights.append("- Youth viewership direction is unavailable because the current filter only includes one monthly period.")
    insights.append(f"- Overall, **{influencer_vs_pg}**.")

    st.markdown("\n".join(insights[:4]))

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
    st.subheader("Filters")

    tt_date_range = st.selectbox(
        "Select Date Range",
        ["All Time", "Last 30 Days", "Last 90 Days", "Custom Range"],
        key="tt_date_range",
    )

    df_tt_filtered = df_tt.copy()

    if tt_date_range == "Last 30 Days":
        tt_cutoff = pd.Timestamp.today().normalize() - pd.Timedelta(days=30)
        df_tt_filtered = df_tt[df_tt["date"] >= tt_cutoff]
    elif tt_date_range == "Last 90 Days":
        tt_cutoff = pd.Timestamp.today().normalize() - pd.Timedelta(days=90)
        df_tt_filtered = df_tt[df_tt["date"] >= tt_cutoff]
    elif tt_date_range == "Custom Range":
        tt_min_date = df_tt["date"].min().date()
        tt_max_date = df_tt["date"].max().date()
        tt_custom_range = st.date_input(
            "Select Custom Date Range",
            value=(tt_min_date, tt_max_date),
            min_value=tt_min_date,
            max_value=tt_max_date,
            key="tt_custom_date_range",
        )

        if isinstance(tt_custom_range, tuple) and len(tt_custom_range) == 2:
            tt_start_date, tt_end_date = tt_custom_range
        elif isinstance(tt_custom_range, list) and len(tt_custom_range) == 2:
            tt_start_date, tt_end_date = tt_custom_range
        elif tt_custom_range:
            tt_start_date = tt_custom_range
            tt_end_date = tt_max_date
        else:
            tt_start_date, tt_end_date = tt_min_date, tt_max_date

        tt_start_ts = pd.Timestamp(tt_start_date)
        tt_end_ts = pd.Timestamp(tt_end_date) + pd.Timedelta(days=1) - pd.Timedelta(microseconds=1)
        df_tt_filtered = df_tt[
            (df_tt["date"] >= tt_start_ts) & (df_tt["date"] <= tt_end_ts)
        ]

    st.header("TikTok")
    df_tt_display = df_tt_filtered.copy()
    df_tt_display["save_share_rate"] = (
        (df_tt_display["saves"] + df_tt_display["share"])
        .div(df_tt_display["views"].replace(0, pd.NA))
        .mul(100)
        .fillna(0)
    )

    tt_pg_posted_col = find_column(df_tt_display, "pg_posted", "pg_posted")
    if tt_pg_posted_col is not None:
        tt_pg_posted_raw = df_tt_display[tt_pg_posted_col].astype(str).str.strip().str.lower()
        df_tt_display["pg_posted_flag"] = tt_pg_posted_raw.map(
            {
                "true": True,
                "false": False,
                "yes": True,
                "no": False,
                "1": True,
                "0": False,
            }
        )
    else:
        df_tt_display["pg_posted_flag"] = pd.NA

    df_tt_display["content_source"] = df_tt_display["pg_posted_flag"].map(
        {
            True: "PG Posted",
            False: "Influencer",
        }
    ).fillna("Unknown")

    tt_campaign_col = find_column(df_tt_display, "campaign", "campaign")
    if tt_campaign_col is not None:
        campaign_series = df_tt_display[tt_campaign_col].fillna("Unknown").astype(str)
    else:
        campaign_series = pd.Series(["Unknown"] * len(df_tt_display), index=df_tt_display.index)
    df_tt_display["campaign_label"] = campaign_series

    tt_influencer_df = df_tt_display[df_tt_display["pg_posted_flag"] == False]
    tt_listing_df = df_tt_display[
        df_tt_display["campaign_label"].astype(str).str.strip().str.lower() == "listing"
    ]

    st.subheader("Key Results")
    tt_kr_cols = st.columns(5)

    tt_median_engagement_rate = df_tt_display["engagement_rate"].median()
    tt_median_video_views = df_tt_display["views"].median()
    tt_median_youth_viewership = df_tt_display["percentage_of_youthviewers"].median()
    tt_median_save_share_rate = df_tt_display["save_share_rate"].median()
    tt_median_video_watched = df_tt_display["percentage_of_videowatched"].median()

    with tt_kr_cols[0]:
        render_kr_card(
            "Median Engagement Rate",
            format_percent(tt_median_engagement_rate),
            "",
            "Median across TikTok videos",
            True,
        )
    with tt_kr_cols[1]:
        render_kr_card(
            "Median Views per Video",
            format_number(tt_median_video_views),
            "",
            "Median across TikTok videos",
            True,
        )
    with tt_kr_cols[2]:
        render_kr_card(
            "Median Youth Viewership %",
            format_percent(tt_median_youth_viewership),
            "",
            "Median across TikTok videos",
            True,
        )
    with tt_kr_cols[3]:
        render_kr_card(
            "Median Save + Share Rate",
            format_percent(tt_median_save_share_rate),
            "",
            "Median across TikTok videos",
            True,
        )
    with tt_kr_cols[4]:
        render_kr_card(
            "Median Video Watched %",
            format_percent(tt_median_video_watched),
            "",
            "Median across TikTok videos",
            True,
        )

    st.subheader("Diagnostics")

    tt_monthly_views = (
        df_tt_display.set_index("date").resample("M")["views"].sum().reset_index()
    )
    tt_fig_monthly_views = px.line(
        tt_monthly_views,
        x="date",
        y="views",
        markers=True,
        title="Monthly Views Trend",
    )
    tt_fig_monthly_views.update_layout(xaxis_title="", yaxis_title="Views")

    tt_campaign_metrics = (
        df_tt_display.groupby("campaign_label", dropna=False)
        .agg(
            median_engagement_rate=("engagement_rate", "median"),
            median_save_share_rate=("save_share_rate", "median"),
        )
        .reset_index()
    )
    tt_campaign_metrics["campaign_label"] = tt_campaign_metrics["campaign_label"].fillna("Unknown")

    tt_fig_campaign_engagement = px.bar(
        tt_campaign_metrics.sort_values("median_engagement_rate", ascending=False),
        x="campaign_label",
        y="median_engagement_rate",
        title="Median Engagement Rate by Campaign",
    )
    tt_fig_campaign_engagement.update_layout(xaxis_title="", yaxis_title="Median Engagement Rate (%)")

    tt_fig_campaign_save_share = px.bar(
        tt_campaign_metrics.sort_values("median_save_share_rate", ascending=False),
        x="campaign_label",
        y="median_save_share_rate",
        title="Median Save + Share Rate by Campaign",
    )
    tt_fig_campaign_save_share.update_layout(xaxis_title="", yaxis_title="Median Save + Share Rate (%)")

    tt_youth_source = (
        df_tt_display[df_tt_display["content_source"] != "Unknown"]
        .groupby("content_source")
        .agg(median_youth_viewership=("percentage_of_youthviewers", "median"))
        .reset_index()
    )
    tt_fig_youth_source = px.bar(
        tt_youth_source,
        x="content_source",
        y="median_youth_viewership",
        title="Youth Viewership: PG Posted vs Influencer",
    )
    tt_fig_youth_source.update_layout(xaxis_title="", yaxis_title="Median Youth Viewership (%)")

    tt_top_posts_views = df_tt_display.sort_values(by="views", ascending=False).head(5).copy()
    tt_top_posts_views["post_label"] = tt_top_posts_views["date"].dt.strftime("%d %b %Y")
    tt_fig_top_views = px.bar(
        tt_top_posts_views.sort_values("views"),
        x="views",
        y="post_label",
        orientation="h",
        hover_data=["campaign_label", "engagement_rate", "save_share_rate", "link"],
        title="Top 5 Posts by Views",
    )
    tt_fig_top_views.update_layout(xaxis_title="Views", yaxis_title="")

    tt_top_posts_youth = (
        df_tt_display.sort_values(by="percentage_of_youthviewers", ascending=False).head(5).copy()
    )
    tt_top_posts_youth["post_label"] = tt_top_posts_youth["date"].dt.strftime("%d %b %Y")
    tt_fig_top_youth = px.bar(
        tt_top_posts_youth.sort_values("percentage_of_youthviewers"),
        x="percentage_of_youthviewers",
        y="post_label",
        orientation="h",
        hover_data=["campaign_label", "views", "engagement_rate", "save_share_rate", "link"],
        title="Top 5 Posts by Youth Viewership",
    )
    tt_fig_top_youth.update_layout(xaxis_title="Youth Viewership (%)", yaxis_title="")

    tt_diag_col1, tt_diag_col2 = st.columns(2)
    with tt_diag_col1:
        st.plotly_chart(tt_fig_monthly_views, use_container_width=True)
        st.plotly_chart(tt_fig_campaign_save_share, use_container_width=True)
        st.plotly_chart(tt_fig_top_views, use_container_width=True)
    with tt_diag_col2:
        st.plotly_chart(tt_fig_campaign_engagement, use_container_width=True)
        if tt_youth_source.empty:
            st.info("PG Posted vs Influencer comparison is unavailable for the current TikTok data.")
        else:
            st.plotly_chart(tt_fig_youth_source, use_container_width=True)
        st.plotly_chart(tt_fig_top_youth, use_container_width=True)

    st.subheader('Campaign Deep Dive: "listing"')

    tt_deep_dive_col1, tt_deep_dive_col2 = st.columns([1, 2])
    with tt_deep_dive_col1:
        st.markdown("**Listing Summary**")
        st.metric("Median Views", format_number(tt_listing_df["views"].median()))
        st.metric(
            "Median Save + Share Rate",
            format_percent(tt_listing_df["save_share_rate"].median()),
        )
        st.metric(
            "Median Youth Viewership",
            format_percent(tt_listing_df["percentage_of_youthviewers"].median()),
        )

    with tt_deep_dive_col2:
        tt_listing_table = tt_listing_df[
            [
                "date",
                "views",
                "engagement_rate",
                "save_share_rate",
                "percentage_of_youthviewers",
                "link",
            ]
        ].sort_values("date", ascending=False)
        if tt_listing_table.empty:
            st.info('No "listing" campaign posts are available for the current TikTok data.')
        else:
            st.dataframe(tt_listing_table, use_container_width=True)
