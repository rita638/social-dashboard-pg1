import streamlit as st
import pandas as pd
import plotly.express as px
import gspread
from html import escape
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

    sheet_key = st.secrets.get("google_sheet_key")
    sheet_name = st.secrets.get("google_sheet_name", "PG SOCIAL DATA - Master Sheet (Cleaned)")
    if sheet_key:
        workbook = client.open_by_key(sheet_key)
    else:
        workbook = client.open(sheet_name)

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


def existing_columns(df, columns):
    return [col for col in columns if col in df.columns]


def first_words(value, word_count=3):
    words = str(value).strip().split()
    if not words or str(value).strip().lower() in {"", "nan", "none"}:
        return "Untitled post"
    return " ".join(words[:word_count])


def get_filtered_data(df, date_range, start_date=None, end_date=None):
    if date_range == "Whole of Prev. Month":
        current_month_start = pd.Timestamp.today().normalize().replace(day=1)
        previous_month_start = current_month_start - pd.DateOffset(months=1)
        previous_month_end = current_month_start - pd.Timedelta(microseconds=1)
        return df[(df["date"] >= previous_month_start) & (df["date"] <= previous_month_end)]
    if date_range == "Last 30 Days":
        cutoff = pd.Timestamp.today().normalize() - pd.Timedelta(days=30)
        return df[df["date"] >= cutoff]
    if date_range == "Last 90 Days":
        cutoff = pd.Timestamp.today().normalize() - pd.Timedelta(days=90)
        return df[df["date"] >= cutoff]
    if date_range == "Custom Range" and start_date is not None and end_date is not None:
        start_ts = pd.Timestamp(start_date)
        end_ts = pd.Timestamp(end_date) + pd.Timedelta(days=1) - pd.Timedelta(microseconds=1)
        return df[(df["date"] >= start_ts) & (df["date"] <= end_ts)]
    return df.copy()


def parse_custom_range(selection, min_date, max_date):
    if isinstance(selection, (tuple, list)):
        if len(selection) == 2:
            return selection[0], selection[1]
        if len(selection) == 1:
            return selection[0], max_date
    if selection:
        return selection, max_date
    return min_date, max_date


def prepare_extract_data(df):
    extract_df = df.copy()

    if "save_share_rate" not in extract_df.columns and {"saves", "share", "views"}.issubset(extract_df.columns):
        extract_df["save_share_rate"] = (
            (extract_df["saves"] + extract_df["share"])
            .div(extract_df["views"].replace(0, pd.NA))
            .mul(100)
            .fillna(0)
        )

    caption_col = find_column(extract_df, "post_caption", "caption")
    if caption_col is not None:
        extract_df["episode_name"] = extract_df[caption_col].apply(first_words)
    else:
        extract_df["episode_name"] = extract_df["date"].dt.strftime("%d %b %Y")

    campaign_col = find_column(extract_df, "campaign", "campaign")
    if campaign_col is not None:
        extract_df["series_name"] = extract_df[campaign_col].fillna("Unknown").astype(str)
    else:
        extract_df["series_name"] = "Unknown"
    extract_df["series_name"] = extract_df["series_name"].str.strip().replace("", "Unknown")

    return extract_df


def render_extract_scorecard(label, value, delta, is_good):
    delta_class = "good" if is_good else "bad"
    st.markdown(
        f"""
        <div class="extract-scorecard">
            <div class="extract-card-label">{escape(label)}</div>
            <div class="extract-card-value">{escape(value)}</div>
            <div class="extract-delta {delta_class}">{escape(delta)}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def make_extract_bar(
    df,
    x,
    y,
    title,
    target=None,
    orientation="v",
    color_col=None,
    x_title="",
    y_title="",
):
    color_sequence = ["#A32D2D", "#8F8E88", "#D3D1C7", "#C96D3B", "#6F7F82"]
    fig = px.bar(
        df,
        x=x,
        y=y,
        orientation=orientation,
        color=color_col,
        color_discrete_sequence=color_sequence,
        title=title,
    )
    fig.update_layout(
        template="plotly_dark",
        paper_bgcolor="#2D2D2A",
        plot_bgcolor="#2D2D2A",
        font={"color": "#F5F1EA", "size": 12},
        title={"font": {"size": 15}},
        legend_title_text="",
        margin={"l": 12, "r": 12, "t": 48, "b": 24},
        xaxis_title=x_title,
        yaxis_title=y_title,
    )
    fig.update_traces(marker_line_width=0)
    fig.update_xaxes(gridcolor="rgba(245,241,234,0.12)")
    fig.update_yaxes(gridcolor="rgba(245,241,234,0.12)")
    if target is not None:
        if orientation == "h":
            fig.add_vline(x=target, line_dash="dash", line_color="#D43C3C")
        else:
            fig.add_hline(y=target, line_dash="dash", line_color="#D43C3C")
    return fig


def render_extract_tab(df, platform_label, platform_short, key_prefix, views_target):
    st.markdown(
        """
        <style>
        .extract-shell { color: #F5F1EA; }
        .extract-title { font-size: 1.35rem; font-weight: 700; margin-top: 0.75rem; }
        .extract-sub { color: #B8B4AB; font-size: 0.95rem; margin-bottom: 1.35rem; }
        .extract-section { color: #AAA59B; font-size: 0.78rem; font-weight: 700; letter-spacing: 0.08em; text-transform: uppercase; margin: 2rem 0 0.8rem; }
        .extract-highlight { background: #FCEBEB; border-left: 4px solid #A32D2D; padding: 0.9rem 1rem; margin: 1rem 0 1.5rem; }
        .extract-highlight-label { color: #7A1D1D; font-size: 0.75rem; font-weight: 700; margin-bottom: 0.25rem; }
        .extract-highlight-title { color: #501313; font-weight: 700; font-size: 0.95rem; }
        .extract-highlight-sub { color: #7A1D1D; font-size: 0.85rem; margin-top: 0.2rem; }
        .extract-scorecard { background: #242421; border-radius: 8px; padding: 1rem; min-height: 7.4rem; }
        .extract-card-label { color: #B8B4AB; font-size: 0.78rem; min-height: 2rem; }
        .extract-card-value { color: #FFFFFF; font-size: 1.55rem; font-weight: 800; line-height: 1.1; }
        .extract-delta { font-size: 0.84rem; margin-top: 0.35rem; }
        .extract-delta.good { color: #1D9E75; }
        .extract-delta.bad { color: #D85A30; }
        </style>
        """,
        unsafe_allow_html=True,
    )

    st.subheader("Filters")
    date_range = st.selectbox(
        "Select Date Range",
        ["All Time", "Whole of Prev. Month", "Last 30 Days", "Last 90 Days", "Custom Range"],
        key=f"{key_prefix}_extract_date_range",
    )

    start_date = None
    end_date = None
    if date_range == "Custom Range":
        min_date = df["date"].min().date()
        max_date = df["date"].max().date()
        custom_range = st.date_input(
            "Select Custom Date Range",
            value=(min_date, max_date),
            min_value=min_date,
            max_value=max_date,
            key=f"{key_prefix}_extract_custom_date_range",
        )
        start_date, end_date = parse_custom_range(custom_range, min_date, max_date)

    extract_df = prepare_extract_data(get_filtered_data(df, date_range, start_date, end_date))
    if extract_df.empty:
        st.info(f"No {platform_label} posts are available for the selected extract period.")
        return

    latest_month = extract_df["date"].max().strftime("%B %Y")
    top_post = extract_df.sort_values("views", ascending=False).iloc[0]
    avg_views = extract_df["views"].mean()
    save_share_median = extract_df["save_share_rate"].median()
    engagement_median = extract_df["engagement_rate"].median()
    youth_median = extract_df["percentage_of_youthviewers"].median()

    st.markdown(
        f"""
        <div class="extract-shell">
            <div class="extract-title">Monthly snapshot - {escape(latest_month)}</div>
            <div class="extract-sub">Auto-generated from {escape(platform_label)} data. Filter by date range above, then copy charts into your newsletter.</div>
            <div class="extract-highlight">
                <div class="extract-highlight-label">Star of the month</div>
                <div class="extract-highlight-title">{escape(top_post["episode_name"])}</div>
                <div class="extract-highlight-sub">Highest views this period · {int(top_post["views"]):,} views</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown('<div class="extract-section">Scorecard vs targets</div>', unsafe_allow_html=True)
    score_cols = st.columns(4)
    with score_cols[0]:
        render_extract_scorecard(
            f"Avg views / video ({platform_short})",
            format_number(avg_views),
            f"{format_views_delta(avg_views, views_target)} vs {views_target:,} target",
            avg_views >= views_target,
        )
    with score_cols[1]:
        render_extract_scorecard(
            "Median engagement rate",
            format_percent(engagement_median),
            "Newsletter context metric",
            True,
        )
    with score_cols[2]:
        render_extract_scorecard(
            "Save + share rate",
            format_percent(save_share_median),
            f"{format_percent_delta(save_share_median, 2.0)} vs 2% target",
            save_share_median >= 2.0,
        )
    with score_cols[3]:
        render_extract_scorecard(
            "Gen Z viewership",
            format_percent(youth_median),
            f"{format_percent_delta(youth_median, 6.0)} vs 6% target",
            youth_median >= 6.0,
        )

    st.markdown('<div class="extract-section">Series comparison</div>', unsafe_allow_html=True)
    series_views = (
        extract_df.groupby("series_name", dropna=False)
        .agg(avg_views=("views", "mean"))
        .reset_index()
        .sort_values("avg_views", ascending=False)
    )
    st.plotly_chart(
        make_extract_bar(
            series_views,
            x="series_name",
            y="avg_views",
            title=f"Avg views per video by series - {platform_short}",
            target=views_target,
            x_title="",
            y_title="Avg views",
        ),
        use_container_width=True,
    )

    st.markdown('<div class="extract-section">Episode performance</div>', unsafe_allow_html=True)
    episode_views = (
        extract_df.sort_values("views", ascending=False)
        .head(12)
        .sort_values("views", ascending=True)
    )
    st.plotly_chart(
        make_extract_bar(
            episode_views,
            x="views",
            y="episode_name",
            title="Views per episode",
            target=views_target,
            orientation="h",
            color_col="series_name",
            x_title="Views",
            y_title="",
        ),
        use_container_width=True,
    )

    st.markdown('<div class="extract-section">Engagement quality</div>', unsafe_allow_html=True)
    quality_cols = st.columns(2)
    quality_df = extract_df.sort_values("views", ascending=False).head(10)
    with quality_cols[0]:
        st.plotly_chart(
            make_extract_bar(
                quality_df.sort_values("save_share_rate", ascending=False),
                x="episode_name",
                y="save_share_rate",
                title="Save + share rate by episode",
                target=2.0,
                color_col="series_name",
                x_title="",
                y_title="Save + share rate (%)",
            ),
            use_container_width=True,
        )
    with quality_cols[1]:
        st.plotly_chart(
            make_extract_bar(
                quality_df.sort_values("percentage_of_youthviewers", ascending=False),
                x="episode_name",
                y="percentage_of_youthviewers",
                title="Gen Z viewership % by episode",
                target=6.0,
                color_col="series_name",
                x_title="",
                y_title="Youth viewership (%)",
            ),
            use_container_width=True,
        )


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
        "save_share_rate",
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

tab1, tab2, tab3, tab4 = st.tabs(["Instagram", "TikTok", "IG Extract", "TT Extract"])

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
        ["All Time", "Whole of Prev. Month", "Last 30 Days", "Last 90 Days", "Custom Range"]
    )

    df_ig_filtered = df_ig.copy()

    if date_range == "Whole of Prev. Month":
        df_ig_filtered = get_filtered_data(df_ig, date_range)
    elif date_range == "Last 30 Days":
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

        start_date, end_date = parse_custom_range(custom_range, min_date, max_date)

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

    ig_pg_posted_col = find_column(df_ig_display, "pg_posted", "pg_posted")
    if ig_pg_posted_col is not None:
        pg_posted_raw = df_ig_display[ig_pg_posted_col].astype(str).str.strip().str.lower()
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
    else:
        df_ig_display["pg_posted_flag"] = pd.NA
    df_ig_display["content_source"] = df_ig_display["pg_posted_flag"].map(
        {
            True: "PG Posted",
            False: "Influencer",
        }
    ).fillna("Unknown")

    ig_campaign_col = find_column(df_ig_display, "campaign", "campaign")
    if ig_campaign_col is not None:
        ig_campaign_series = df_ig_display[ig_campaign_col].fillna("Unknown").astype(str)
    else:
        ig_campaign_series = pd.Series(["Unknown"] * len(df_ig_display), index=df_ig_display.index)
    df_ig_display["campaign_label"] = ig_campaign_series

    influencer_df = df_ig_display[df_ig_display["pg_posted_flag"] == False]
    listing_df = df_ig_display[
        df_ig_display["campaign_label"].astype(str).str.strip().str.lower() == "listing"
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
        df_ig_display.set_index("date").resample("MS")["views"].sum().reset_index()
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
        df_ig_display.groupby("campaign_label", dropna=False)
        .agg(
            median_engagement_rate=("engagement_rate", "median"),
            median_save_share_rate=("save_share_rate", "median"),
        )
        .reset_index()
    )
    campaign_metrics["campaign_label"] = campaign_metrics["campaign_label"].fillna("Unknown")
    campaign_metrics = campaign_metrics.sort_values("campaign_label")

    fig_campaign_engagement = px.bar(
        campaign_metrics.sort_values("median_engagement_rate", ascending=False),
        x="campaign_label",
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
        x="campaign_label",
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
        hover_data=existing_columns(
            top_youth_posts,
            ["campaign_label", "views", "engagement_rate", "save_share_rate", "link"],
        ),
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
        .resample("MS")["percentage_of_youthviewers"]
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
            f"- Top campaign by median engagement is **{top_campaign.iloc[0]['campaign_label']}** at **{top_campaign.iloc[0]['median_engagement_rate']:.2f}%**."
        )
    if not lowest_campaign.empty:
        insights.append(
            f"- Lowest campaign by median engagement is **{lowest_campaign.iloc[0]['campaign_label']}** at **{lowest_campaign.iloc[0]['median_engagement_rate']:.2f}%**."
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
        listing_table_columns = existing_columns(
            listing_df,
            [
                "date",
                "views",
                "engagement_rate",
                "save_share_rate",
                "percentage_of_youthviewers",
                "link",
            ]
        )
        listing_table = listing_df[listing_table_columns].sort_values("date", ascending=False)
        if listing_table.empty:
            st.info('No "listing" campaign posts are available for the current Instagram date filter.')
        else:
            st.dataframe(listing_table, use_container_width=True)

with tab2:
    st.subheader("Filters")

    tt_date_range = st.selectbox(
        "Select Date Range",
        ["All Time", "Whole of Prev. Month", "Last 30 Days", "Last 90 Days", "Custom Range"],
        key="tt_date_range",
    )

    df_tt_filtered = df_tt.copy()

    if tt_date_range == "Whole of Prev. Month":
        df_tt_filtered = get_filtered_data(df_tt, tt_date_range)
    elif tt_date_range == "Last 30 Days":
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

        tt_start_date, tt_end_date = parse_custom_range(tt_custom_range, tt_min_date, tt_max_date)

        tt_start_ts = pd.Timestamp(tt_start_date)
        tt_end_ts = pd.Timestamp(tt_end_date) + pd.Timedelta(days=1) - pd.Timedelta(microseconds=1)
        df_tt_filtered = df_tt[
            (df_tt["date"] >= tt_start_ts) & (df_tt["date"] <= tt_end_ts)
        ]

    st.header("TikTok")
    df_tt_display = df_tt_filtered.copy()
    if "save_share_rate" not in df_tt_display.columns:
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
        df_tt_display.set_index("date").resample("MS")["views"].sum().reset_index()
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
        hover_data=existing_columns(
            tt_top_posts_views,
            ["campaign_label", "engagement_rate", "save_share_rate", "link"],
        ),
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
        hover_data=existing_columns(
            tt_top_posts_youth,
            ["campaign_label", "views", "engagement_rate", "save_share_rate", "link"],
        ),
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
        tt_listing_table_columns = existing_columns(
            tt_listing_df,
            [
                "date",
                "views",
                "engagement_rate",
                "save_share_rate",
                "percentage_of_youthviewers",
                "link",
            ]
        )
        tt_listing_table = tt_listing_df[tt_listing_table_columns].sort_values("date", ascending=False)
        if tt_listing_table.empty:
            st.info('No "listing" campaign posts are available for the current TikTok data.')
        else:
            st.dataframe(tt_listing_table, use_container_width=True)

with tab3:
    render_extract_tab(df_ig, "Instagram", "IG", "ig", 6000)

with tab4:
    render_extract_tab(df_tt, "TikTok", "TT", "tt", 3000)
