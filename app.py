from __future__ import annotations

import hashlib
from datetime import date
from typing import Any
from urllib.parse import urlparse

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from analysis import association_summary, parse_csv_bytes, prepare_analysis_data, summarize_numeric


st.set_page_config(
    page_title="UrbanHeat Analytics | Mumbai",
    page_icon="🌡",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
      [data-testid="stAppViewContainer"] { background: #f5f7f3; }
      [data-testid="stSidebar"] { background: #edf2eb; border-right: 1px solid #dce5dc; }
      [data-testid="stHeader"] { background: transparent; }
      .block-container { max-width: 1480px; padding-top: 2rem; padding-bottom: 3rem; }
      .uh-eyebrow { color: #54705d; font-size: .78rem; font-weight: 700; letter-spacing: .12em; text-transform: uppercase; }
      .uh-subtitle { color: #58665c; font-size: 1.05rem; margin-top: -.3rem; }
      .uh-research-tag { color: #405748; font-size: .78rem; font-weight: 650; letter-spacing: .04em; }
      div[data-testid="stMetric"] { background: #fff; border: 1px solid #e1e8e0; border-radius: 10px; padding: .8rem 1rem; }
      div[data-testid="stMetricLabel"] p { color: #526157; }
      div[data-testid="stAlert"] { border-radius: 9px; }
      h1, h2, h3 { color: #203c2d; }
      a { color: #285c40; }
    </style>
    """,
    unsafe_allow_html=True,
)

st.markdown('<div class="uh-eyebrow">Applied Data Analysis · Mumbai, India</div>', unsafe_allow_html=True)
st.title("UrbanHeat Analytics")
st.markdown(
    '<div class="uh-subtitle">Exploring urban heat patterns through data</div>',
    unsafe_allow_html=True,
)

st.sidebar.markdown("## Study setup")
st.sidebar.caption("Upload a documented CSV. Source observations are kept separate from the analytical view.")
uploaded_file = st.sidebar.file_uploader("Research data (CSV)", type=["csv"], help="Upload a locally downloaded CSV. The app does not fetch or invent observations.")

raw: pd.DataFrame | None = None
upload_error: str | None = None
dataset_key = "no-upload"
if uploaded_file is not None:
    payload = uploaded_file.getvalue()
    dataset_key = hashlib.sha256(payload).hexdigest()[:12]
    if len(payload) > 50 * 1024 * 1024:
        upload_error = "This file is larger than the 50 MB limit. Export a smaller study-area subset and try again."
    else:
        try:
            raw = parse_csv_bytes(payload)
        except ValueError as exc:
            upload_error = str(exc)

column_names = list(raw.columns) if raw is not None else []
column_options = ["— Not selected —", *[str(name) for name in column_names]]

source_name = ""
source_url = ""
dataset_area = ""
dataset_period = ""
acquired_on: date | None = None
spatial_resolution = ""
temporal_resolution = ""
temperature_definition = "Not specified"
temperature_unit = "Not documented"
other_unit = ""
vegetation_type = "Not specified"
mapping: dict[str, Any] = {}

if raw is not None:
    st.sidebar.markdown("### Dataset record")
    source_name = st.sidebar.text_input("Source or dataset name", placeholder="As stated by the provider", key=f"source_name_{dataset_key}")
    source_url = st.sidebar.text_input("Source / dataset URL", placeholder="https://…", key=f"source_url_{dataset_key}")
    dataset_area = st.sidebar.text_input("Study area stated in the source", placeholder="Do not assume Mumbai coverage", key=f"dataset_area_{dataset_key}")
    dataset_period = st.sidebar.text_input("Documented period", placeholder="e.g. YYYY–YYYY or acquisition dates", key=f"dataset_period_{dataset_key}")
    acquired_on = st.sidebar.date_input("Date you acquired this file", value=None, key=f"acquired_on_{dataset_key}")
    spatial_resolution = st.sidebar.text_input("Documented spatial resolution", placeholder="Leave blank if unknown", key=f"spatial_resolution_{dataset_key}")
    temporal_resolution = st.sidebar.text_input("Documented temporal resolution", placeholder="Leave blank if unknown", key=f"temporal_resolution_{dataset_key}")

    st.sidebar.markdown("### Declare the temperature measure")
    temperature_definition = st.sidebar.selectbox(
        "Measurement definition",
        ["Not specified", "Land-surface temperature", "Air temperature", "Heat index", "Other heat metric"],
        key=f"temperature_definition_{dataset_key}",
        help="Use one documented measure only. Different heat metrics are not combined.",
    )
    temperature_unit = st.sidebar.selectbox(
        "Temperature unit",
        ["Not documented", "°C", "°F", "K", "Other"],
        key=f"temperature_unit_{dataset_key}",
    )
    if temperature_unit == "Other":
        other_unit = st.sidebar.text_input("Unit as documented", placeholder="Exact unit label", key=f"other_temperature_unit_{dataset_key}")

    st.sidebar.markdown("### Map CSV columns")

    def select_column(label: str, field: str, help_text: str = "") -> str | None:
        choice = st.sidebar.selectbox(
            label,
            column_options,
            index=0,
            key=f"column_{dataset_key}_{field}",
            help=help_text or None,
        )
        return None if choice == "— Not selected —" else choice

    mapping["temperature"] = select_column(
        "Temperature values *", "temperature", "Choose the column containing one consistent, documented temperature measure."
    )
    mapping["date"] = select_column("Observation date / time", "date")
    date_convention = st.sidebar.selectbox(
        "Date order for ambiguous values",
        ["Month-first / ISO", "Day-first (DD/MM/YYYY)"],
        key=f"date_convention_{dataset_key}",
        help="Check this against the provider's date format. ISO YYYY-MM-DD is unambiguous.",
    )
    mapping["date_dayfirst"] = date_convention == "Day-first (DD/MM/YYYY)"
    mapping["location"] = select_column("Location or category", "location")
    mapping["latitude"] = select_column("Latitude", "latitude")
    mapping["longitude"] = select_column("Longitude", "longitude")
    mapping["vegetation"] = select_column("Vegetation measure", "vegetation")
    vegetation_type = st.sidebar.selectbox(
        "Vegetation definition",
        ["Not specified", "NDVI", "Other numeric vegetation metric"],
        key=f"vegetation_type_{dataset_key}",
        help="NDVI analysis is enabled only when the uploaded values are documented as unscaled NDVI in the range −1 to 1.",
    )
    mapping["vegetation_type"] = vegetation_type

analysis_frame: pd.DataFrame | None = None
derived: dict[str, str] = {}
quality: dict[str, int] = {}
mapping_error: str | None = None
if raw is not None and not raw.empty and mapping.get("temperature"):
    try:
        analysis_frame, derived, quality = prepare_analysis_data(raw, mapping)
    except ValueError as exc:
        mapping_error = str(exc)
elif raw is not None:
    try:
        analysis_frame, derived, quality = prepare_analysis_data(raw, mapping)
    except ValueError as exc:
        mapping_error = str(exc)

temperature_unit_label = other_unit.strip() if temperature_unit == "Other" and other_unit.strip() else temperature_unit
if temperature_unit_label == "Other":
    temperature_unit_label = "unit not documented"
if temperature_unit_label == "Not documented":
    temperature_unit_label = "source unit not documented"
temperature_axis_label = f"Temperature ({temperature_unit_label})"

filtered: pd.DataFrame | None = None
filter_note: list[str] = []

if raw is not None and analysis_frame is not None:
    filtered = analysis_frame.copy()
    st.sidebar.markdown("### Optional analysis filters")
    date_alias = derived.get("date")
    if date_alias:
        available_dates = filtered[date_alias].dropna()
        if not available_dates.empty:
            start_date = available_dates.min().date()
            end_date = available_dates.max().date()
            chosen_dates = st.sidebar.date_input(
                "Date range",
                value=(start_date, end_date),
                min_value=start_date,
                max_value=end_date,
                key=f"analysis_date_range_{dataset_key}_{date_alias}_{start_date}_{end_date}",
            )
            if isinstance(chosen_dates, (tuple, list)) and len(chosen_dates) == 2:
                start, end = chosen_dates
                filtered = filtered[
                    filtered[date_alias].dt.date.between(start, end)
                ]
                if start != start_date or end != end_date:
                    filter_note.append(f"dates {start} to {end}")

    group_column = mapping.get("location")
    if group_column:
        categories = raw[group_column].dropna().astype(str).unique().tolist()
        if 0 < len(categories) <= 100:
            selected_categories = st.sidebar.multiselect(
                "Location / category",
                categories,
                default=categories,
                key=f"analysis_categories_{dataset_key}_{group_column}",
            )
            filtered = filtered[
                filtered[group_column].astype("string").isin(selected_categories)
            ]
            if len(selected_categories) != len(categories):
                filter_note.append(f"{len(selected_categories)} selected categories")
        elif len(categories) > 100:
            st.sidebar.caption("Category filter hidden: more than 100 distinct values.")

if upload_error:
    st.error(upload_error)
elif raw is None:
    st.info("Upload a real, documented CSV in the sidebar to begin. No example observations or placeholder statistics are shown.")
elif raw.empty:
    st.warning("The CSV has headers but no observation rows. Upload a non-empty dataset to calculate analyses.")
elif mapping_error:
    st.error(mapping_error)

overview_tab, temperature_tab, vegetation_tab, geography_tab, explorer_tab, methods_tab = st.tabs(
    [
        "Research Overview",
        "Temperature Analysis",
        "Vegetation Analysis",
        "Geographic Explorer",
        "Data Explorer",
        "Methodology & Sources",
    ]
)

with overview_tab:
    st.subheader("Research question")
    st.write(
        "How do land-surface temperatures vary across the selected urban study area, "
        "and what relationships exist between temperature, vegetation, location, and time?"
    )
    st.write(
        "This applied data analysis examines uploaded observations for the study area and period "
        "documented by the source. It describes patterns in the supplied sample; it does not forecast "
        "weather or assume that a sample represents all of Mumbai."
    )

    if raw is not None:
        st.markdown("### Uploaded dataset")
        info_cols = st.columns(4)
        info_cols[0].metric("Rows in source", f"{len(raw):,}")
        info_cols[1].metric("Columns", f"{len(raw.columns):,}")
        info_cols[2].metric("Duplicate rows", f"{int(raw.duplicated().sum()):,}")
        if mapping.get("temperature") and quality:
            invalid_total = quality.get("temperature_missing", 0) + quality.get("temperature_invalid", 0)
            info_cols[3].metric("Missing / invalid temperature", f"{invalid_total:,}")
        else:
            info_cols[3].metric("Temperature mapping", "Not selected")

        if source_name or dataset_area or dataset_period:
            st.caption(
                " · ".join(
                    text for text in [
                        source_name or None,
                        dataset_area or None,
                        dataset_period or None,
                    ] if text
                )
            )
        if source_url.strip():
            parsed_source_url = urlparse(source_url.strip())
            if parsed_source_url.scheme in {"http", "https"} and parsed_source_url.netloc:
                st.link_button("Open supplied source URL", parsed_source_url.geturl())
            else:
                st.caption(f"Source URL as entered (not a valid HTTP/HTTPS link): {source_url.strip()}")

        if mapping.get("temperature") and quality.get("temperature_usable", 0) > 0:
            values = analysis_frame[derived["temperature"]]
            stats = summarize_numeric(values)
            st.markdown("### Temperature summary")
            summary_cols = st.columns(4)
            summary_cols[0].metric("Usable observations", f"{stats['count']:,}")
            summary_cols[1].metric(
                f"Mean · {temperature_unit_label}",
                f"{stats['mean']:,.2f}",
            )
            summary_cols[2].metric(
                f"Median · {temperature_unit_label}",
                f"{stats['median']:,.2f}",
            )
            summary_cols[3].metric(
                f"Range · {temperature_unit_label}",
                f"{stats['min']:,.2f} – {stats['max']:,.2f}",
            )

            available_dates = analysis_frame[derived["date"]].dropna() if derived.get("date") else pd.Series(dtype="datetime64[ns]")
            available_locations = (
                raw[mapping["location"]].nunique(dropna=True)
                if mapping.get("location")
                else None
            )
            details = [f"Measurement: {temperature_definition}"]
            if derived.get("date") and not available_dates.empty:
                details.append(
                    f"parsed date coverage: {available_dates.min().date()} to {available_dates.max().date()}"
                )
            if available_locations is not None:
                details.append(f"unique non-missing locations/categories: {available_locations:,}")
            st.caption(" · ".join(details))
            if temperature_definition == "Not specified":
                st.warning("Temperature values are calculated from the selected column, but its measurement definition is not documented.")
            if temperature_unit_label == "source unit not documented":
                st.warning("The source unit is unknown. Values are labeled as source units and are not converted.")
            if filter_note:
                st.caption("Analysis filters active: " + ", ".join(filter_note) + ". Dataset metrics above use the full uploaded file.")
        elif mapping.get("temperature"):
            st.warning("The selected temperature field has no usable numeric values. No temperature statistics or charts are shown.")
        else:
            st.warning("Choose the temperature column in the sidebar to calculate temperature summaries.")

        st.markdown("### Original data preview")
        st.caption("The preview is the uploaded source, before parsing or cleaning.")
        st.dataframe(raw.head(8), width="stretch", hide_index=True)
    else:
        st.markdown("### How to start")
        st.markdown(
            """
            1. Obtain a CSV through a documented data-provider workflow and keep its source metadata.
            2. Upload it in the sidebar and map the relevant fields.
            3. Declare the temperature definition and unit exactly as documented.
            4. Review validation counts before interpreting the calculated charts.
            """
        )
        st.info(
            "The BHRIGU explorer describes national heat datasets for 2002–2025 at 1 km × 1 km, "
            "but the provider landing page does not document a direct CSV/API download. Use only an "
            "export the portal explicitly offers; do not scrape or assume an endpoint."
        )

with temperature_tab:
    st.subheader("Temperature Analysis")
    if raw is None:
        st.info("Upload a documented CSV to view temperature analysis.")
    elif not mapping.get("temperature"):
        st.warning("Select the temperature column in the sidebar.")
    elif not quality.get("temperature_usable", 0):
        st.warning("No finite numeric temperature values are available in the selected column.")
    elif filtered is not None:
        temp_alias = derived["temperature"]
        plot_data = filtered.dropna(subset=[temp_alias])
        if plot_data.empty:
            st.warning("No temperature observations remain after the current filters.")
        else:
            stats = summarize_numeric(plot_data[temp_alias])
            st.caption(
                f"{stats['count']:,} valid observations · {temperature_definition} · "
                f"{temperature_unit_label}. Invalid and missing values are excluded from calculations, not deleted from the source."
            )
            if quality.get("temperature_missing", 0) or quality.get("temperature_invalid", 0):
                st.warning(
                    f"Full file: {quality.get('temperature_missing', 0):,} missing and "
                    f"{quality.get('temperature_invalid', 0):,} non-numeric or non-finite temperature values."
                )

            stat_table = pd.DataFrame(
                {
                    "Statistic": ["Count", "Mean", "Median", "Standard deviation", "Minimum", "25th percentile", "75th percentile", "Maximum"],
                    f"Value ({temperature_unit_label})": [
                        stats["count"], stats["mean"], stats["median"], stats["std"],
                        stats["min"], stats["q25"], stats["q75"], stats["max"],
                    ],
                }
            )
            st.dataframe(stat_table, hide_index=True, width="stretch")

            left, right = st.columns(2)
            with left:
                histogram = px.histogram(
                    plot_data,
                    x=temp_alias,
                    nbins=30,
                    labels={temp_alias: temperature_axis_label, "count": "Observations"},
                    color_discrete_sequence=["#c86d3d"],
                    title="Observed temperature distribution",
                )
                histogram.update_layout(template="plotly_white", bargap=0.06, margin=dict(l=10, r=10, t=55, b=10))
                st.plotly_chart(histogram, width="stretch")
            with right:
                box = px.box(
                    plot_data,
                    y=temp_alias,
                    labels={temp_alias: temperature_axis_label},
                    color_discrete_sequence=["#3b7050"],
                    points="outliers",
                    title="Spread and potential outliers",
                )
                box.update_layout(template="plotly_white", margin=dict(l=10, r=10, t=55, b=10))
                st.plotly_chart(box, width="stretch")

            difference = float(stats["mean"]) - float(stats["median"])
            direction = "above" if difference > 0 else "below" if difference < 0 else "equal to"
            st.markdown("**Calculated interpretation**")
            st.write(
                f"For the {stats['count']:,} valid observations currently shown, the mean "
                f"({stats['mean']:.2f}) is {abs(difference):.2f} {temperature_unit_label} "
                f"{direction} the median ({stats['median']:.2f}). The observed range is "
                f"{stats['min']:.2f}–{stats['max']:.2f} {temperature_unit_label}. "
                "This describes the uploaded sample only."
            )

            if derived.get("date"):
                dated = plot_data.dropna(subset=[derived["date"]]).copy()
                if not dated.empty:
                    dated["_observation_date"] = dated[derived["date"]].dt.date
                    daily = (
                        dated.groupby("_observation_date", as_index=False)
                        .agg(
                            daily_mean=(temp_alias, "mean"),
                            observations=(temp_alias, "size"),
                        )
                    )
                    if len(daily) >= 1:
                        time_fig = px.line(
                            daily,
                            x="_observation_date",
                            y="daily_mean",
                            markers=True,
                            hover_data={"observations": True},
                            labels={
                                "_observation_date": "Observation date",
                                "daily_mean": temperature_axis_label,
                                "observations": "Valid observations",
                            },
                            title="Daily mean of uploaded observations",
                        )
                        time_fig.update_traces(line_color="#3b7050")
                        time_fig.update_layout(template="plotly_white", margin=dict(l=10, r=10, t=55, b=10))
                        st.plotly_chart(time_fig, width="stretch")
                        st.caption("Daily means aggregate only the uploaded, filtered observations for each represented date; they are not city-wide estimates unless the source sample supports that scope.")
                if quality.get("date_invalid", 0):
                    st.caption(f"{quality['date_invalid']:,} non-empty date values in the full file could not be parsed.")

            excluded_categories = {
                mapping.get("temperature"),
                mapping.get("date"),
                mapping.get("latitude"),
                mapping.get("longitude"),
                mapping.get("vegetation"),
            }
            category_candidates = [
                str(column)
                for column in raw.columns
                if str(column) not in excluded_categories
                and raw[column].nunique(dropna=True) <= 30
                and raw[column].nunique(dropna=True) > 1
            ]
            if category_candidates:
                default_index = category_candidates.index(mapping["location"]) if mapping.get("location") in category_candidates else 0
                compare_column = st.selectbox(
                    "Compare observations by location or category",
                    category_candidates,
                    index=default_index,
                    key=f"comparison_column_{dataset_key}",
                )
                compare_data = plot_data.dropna(subset=[compare_column])
                if not compare_data.empty:
                    compare_fig = px.box(
                        compare_data,
                        x=compare_column,
                        y=temp_alias,
                        color=compare_column,
                        labels={temp_alias: temperature_axis_label, compare_column: "Location / category"},
                        points="outliers",
                        title=f"Temperature spread by {compare_column}",
                    )
                    compare_fig.update_layout(template="plotly_white", showlegend=False, margin=dict(l=10, r=10, t=55, b=10))
                    st.plotly_chart(compare_fig, width="stretch")
                    st.caption("Groups are compared only within this uploaded dataset. This is not a controlled or causal comparison.")

with vegetation_tab:
    st.subheader("Vegetation Analysis")
    if raw is None:
        st.info("Upload a dataset to assess whether a compatible vegetation measure is available.")
    elif not mapping.get("vegetation"):
        st.info(
            "No vegetation column is mapped. To examine vegetation–temperature association, upload a compatible "
            "vegetation observation (for example, documented NDVI) aligned to the same locations and dates as the temperature data."
        )
    elif vegetation_type != "NDVI":
        st.info(
            "The selected vegetation field is not declared as unscaled NDVI. This app does not infer or rescale vegetation values; "
            "provide a documented NDVI column to enable this analysis."
        )
    elif not mapping.get("temperature"):
        st.warning("Select a temperature column to pair it with NDVI.")
    elif filtered is not None:
        temp_alias = derived["temperature"]
        vegetation_alias = derived.get("vegetation")
        if vegetation_alias is None:
            st.warning("No valid NDVI analytical column is available.")
        else:
            paired = filtered[[temp_alias, vegetation_alias]].dropna()
            invalid_ndvi = quality.get("vegetation_invalid", 0)
            if invalid_ndvi:
                st.warning(
                    f"{invalid_ndvi:,} non-empty vegetation values in the full file are non-numeric, non-finite, "
                    "or outside the documented NDVI range [−1, 1]; they are excluded, not rescaled."
                )
            if paired.empty:
                st.warning("No rows have both valid temperature and NDVI values after the current filters.")
            else:
                method_label = st.radio(
                    "Association statistic",
                    ["Pearson", "Spearman"],
                    horizontal=True,
                    key=f"vegetation_correlation_method_{dataset_key}",
                    help="Pearson measures linear association; Spearman measures monotonic rank association.",
                )
                method = method_label.lower()
                association = association_summary(
                    paired[vegetation_alias],
                    paired[temp_alias],
                    method=method,
                )
                stat_cols = st.columns(3)
                stat_cols[0].metric("Complete paired observations", f"{association['n']:,}")
                stat_cols[1].metric(
                    f"{method_label} correlation",
                    "Not calculable" if association["correlation"] is None else f"{association['correlation']:.3f}",
                )
                stat_cols[2].metric("Rows missing one or both values", f"{len(filtered) - association['n']:,}")

                trend = st.checkbox("Add a descriptive linear guide", value=False, key=f"ndvi_trendline_{dataset_key}")
                scatter = px.scatter(
                    paired,
                    x=vegetation_alias,
                    y=temp_alias,
                    labels={
                        vegetation_alias: "NDVI (unitless; source values)",
                        temp_alias: temperature_axis_label,
                    },
                    color_discrete_sequence=["#3b7050"],
                    opacity=0.78,
                    title="NDVI and temperature observations",
                )
                if trend and len(paired) >= 2 and paired[vegetation_alias].nunique() > 1:
                    x_values = paired[vegetation_alias].to_numpy(dtype=float)
                    y_values = paired[temp_alias].to_numpy(dtype=float)
                    slope, intercept = np.polyfit(x_values, y_values, 1)
                    x_line = np.linspace(float(np.min(x_values)), float(np.max(x_values)), 50)
                    scatter.add_trace(
                        go.Scatter(
                            x=x_line,
                            y=slope * x_line + intercept,
                            mode="lines",
                            name="Linear guide",
                            line=dict(color="#c86d3d", dash="dash"),
                        )
                    )
                scatter.update_layout(template="plotly_white", margin=dict(l=10, r=10, t=55, b=10))
                st.plotly_chart(scatter, width="stretch")
                if trend:
                    st.caption("The dashed line is a descriptive least-squares guide, not a causal model.")
                if association["correlation"] is None:
                    st.warning("A correlation requires at least three paired observations with variation in both fields.")
                else:
                    direction = "positive" if association["correlation"] > 0 else "negative" if association["correlation"] < 0 else "near-zero"
                    st.markdown("**Cautious interpretation**")
                    st.write(
                        f"The selected {method_label} coefficient is {association['correlation']:.3f} "
                        f"({direction} association) across {association['n']:,} complete pairs. "
                        "Correlation does not establish causation; spatial and seasonal confounding, measurement "
                        "alignment, and sample coverage remain important."
                    )

with geography_tab:
    st.subheader("Geographic Explorer")
    if raw is None:
        st.info("Upload a CSV with real latitude, longitude, and temperature values to plot observations.")
    elif not mapping.get("latitude") or not mapping.get("longitude"):
        st.info("Map both latitude and longitude columns in the sidebar. No locations are inferred from names.")
    elif not mapping.get("temperature"):
        st.warning("Select the temperature column to color valid coordinates.")
    elif filtered is not None:
        lat_alias = derived.get("latitude")
        lon_alias = derived.get("longitude")
        temp_alias = derived.get("temperature")
        if not lat_alias or not lon_alias:
            st.warning("Both coordinate fields must be mapped to enable the geographic plot.")
        else:
            geo_data = filtered.dropna(subset=[lat_alias, lon_alias, temp_alias])
            invalid_geo = quality.get("coordinates_invalid", 0)
            st.caption(
                f"{quality.get('coordinates_usable', 0):,} valid coordinate pairs in the full file · "
                f"{invalid_geo:,} invalid or incomplete pairs · {len(geo_data):,} plotted observations with valid temperature."
            )
            if geo_data.empty:
                st.warning("No observations have valid coordinates and temperature values after the current filters.")
            else:
                hover_fields = []
                for field in ["date", "location", "vegetation"]:
                    original = mapping.get(field)
                    if original and original not in hover_fields:
                        hover_fields.append(original)
                geo_fig = px.scatter(
                    geo_data,
                    x=lon_alias,
                    y=lat_alias,
                    color=temp_alias,
                    color_continuous_scale=["#3b7050", "#d49a48", "#bd4c37"],
                    hover_data=hover_fields,
                    labels={
                        lon_alias: "Longitude (degrees)",
                        lat_alias: "Latitude (degrees)",
                        temp_alias: temperature_axis_label,
                    },
                    title="Uploaded observations at their recorded coordinates",
                )
                geo_fig.update_traces(marker=dict(size=9, opacity=0.82, line=dict(width=0.5, color="#fff")))
                geo_fig.update_layout(template="plotly_white", margin=dict(l=10, r=10, t=55, b=10))
                geo_fig.update_yaxes(scaleanchor="x", scaleratio=1)
                st.plotly_chart(geo_fig, width="stretch")
                st.caption("Points use only uploaded coordinates. No neighborhood boundaries or citywide coverage are inferred.")
            if invalid_geo:
                st.warning(f"{invalid_geo:,} rows in the full file have missing, non-numeric, or out-of-range coordinates.")

with explorer_tab:
    st.subheader("Data Explorer")
    if raw is None:
        st.info("Upload a CSV to inspect source rows, column types, missing values, duplicates, and cleaning decisions.")
    else:
        st.write(f"Source shape: **{raw.shape[0]:,} rows × {raw.shape[1]:,} columns**.")
        st.write(f"Exact duplicate rows in source: **{int(raw.duplicated().sum()):,}**. Duplicate rows are reported, not removed.")

        column_summary = pd.DataFrame(
            {
                "Column": [str(column) for column in raw.columns],
                "Inferred type": [str(raw[column].dtype) for column in raw.columns],
                "Missing values": [int(raw[column].isna().sum()) for column in raw.columns],
                "Missing (%)": [
                    round(float(raw[column].isna().mean() * 100), 2) if len(raw) else 0.0
                    for column in raw.columns
                ],
                "Unique non-missing": [int(raw[column].nunique(dropna=True)) for column in raw.columns],
            }
        )
        st.markdown("### Columns and missing values")
        st.dataframe(column_summary, width="stretch", hide_index=True)

        st.markdown("### Search uploaded observations")
        search = st.text_input("Find text across source columns", placeholder="Type a date, location, or value")
        shown = raw
        if search.strip():
            search_value = search.strip().casefold()
            mask = raw.astype("string").apply(
                lambda column: column.str.casefold().str.contains(search_value, regex=False, na=False)
            ).any(axis=1)
            shown = raw.loc[mask]
        st.caption(f"Showing {min(len(shown), 500):,} of {len(shown):,} matching rows (500-row display limit).")
        st.dataframe(shown.head(500), width="stretch", hide_index=True)

        st.markdown("### Cleaning and analytical view")
        st.write(
            "The uploaded source is never overwritten. The analytical view adds parsed columns; invalid values become missing "
            "only in those derived columns. No source rows or duplicates are silently discarded."
        )
        decisions = [
            f"All {len(raw):,} source rows are retained.",
            f"{int(raw.duplicated().sum()):,} exact duplicate rows are retained and reported.",
        ]
        if mapping.get("temperature"):
            decisions.append(
                f"Temperature: {quality.get('temperature_missing', 0):,} missing; "
                f"{quality.get('temperature_invalid', 0):,} non-numeric / non-finite; "
                f"{quality.get('temperature_usable', 0):,} usable."
            )
        else:
            decisions.append("No temperature field is mapped; temperature statistics are unavailable.")
        if mapping.get("date"):
            decisions.append(
                f"Dates: {quality.get('date_invalid', 0):,} non-empty values could not be parsed; source strings remain unchanged."
            )
        if mapping.get("latitude") and mapping.get("longitude"):
            decisions.append(
                f"Coordinates: {quality.get('coordinates_invalid', 0):,} incomplete, non-numeric, or out-of-range pairs are excluded from plots."
            )
        elif mapping.get("latitude") or mapping.get("longitude"):
            decisions.append("Only one coordinate axis is mapped; geographic plots are disabled until both are selected.")
        if mapping.get("vegetation"):
            decisions.append(
                f"Vegetation: {quality.get('vegetation_invalid', 0):,} invalid values in the derived field."
            )
        for decision in decisions:
            st.markdown(f"- {decision}")

        clean_copy = raw.copy(deep=True)
        if analysis_frame is not None:
            for name in derived.values():
                if name not in clean_copy.columns:
                    clean_copy[name] = analysis_frame[name]
        st.download_button(
            "Download cleaned analytical CSV",
            data=clean_copy.to_csv(index=False).encode("utf-8"),
            file_name="urbanheat_analytical_data.csv",
            mime="text/csv",
            help="Includes every original row and source column plus available derived analysis fields.",
        )
        st.caption("Analysis filters affect charts only. The CSV export includes all source rows.")

with methods_tab:
    st.subheader("Methodology & Sources")
    st.markdown("### Research question and objectives")
    st.write(
        "The project asks how land-surface temperatures vary across a selected urban study area and how observed "
        "temperature relates to vegetation, location, and time. Objectives are to validate source data, describe "
        "the uploaded observations, examine compatible associations, and communicate limits on interpretation."
    )

    st.markdown("### Verified source information")
    st.markdown(
        """
        **BHRIGU National Heat+ Insights Explorer (CSTEP)** — its official landing page describes national heat
        assessment datasets covering **2002–2025** at **1 km × 1 km**, with multiple heat indices and supporting
        thematic layers across more than 5,000 functional urban areas. The exact selected layer's definition,
        unit, temporal aggregation, and whether Mumbai is included in a particular export must be checked against
        that layer's documentation. The landing page does not document a public CSV/API endpoint; use only an
        export explicitly provided by the portal.

        **USGS Landsat Collection 2 Level-2 Surface Temperature** — official USGS documentation describes
        global scene-based surface-temperature products for Landsat 4–9, measured in Kelvin. The Level-2
        surface-temperature digital number is converted by **ST = (DN × 0.00341802) + 149.0**; the product is
        nominally on a 30 m grid. Scene dates vary by satellite, and the sensors/products are not automatically
        a matched time series. USGS lists downloads through EarthExplorer. Apply product fill-value and quality
        guidance before interpreting pixels.
        """
    )
    st.markdown(
        "- [BHRIGU National Heat+ Insights Explorer](https://bhrigu.cstep.in/)\n"
        "- [CSTEP BHRIGU project overview](https://cstep.in/projects/building-heat-resilience-in-indias-growing-urbanscapes-bhrigu)\n"
        "- [USGS Landsat Collection 2 Surface Temperature](https://www.usgs.gov/landsat-missions/landsat-collection-2-surface-temperature)\n"
        "- [USGS Collection 2 Level-2 science products](https://www.usgs.gov/landsat-missions/landsat-collection-2-level-2-science-products)\n"
        "- [USGS EarthExplorer data access](https://earthexplorer.usgs.gov/)"
    )
    st.caption("Provider facts above were checked against official pages on 25 October 2026. Confirm the current layer/product guide before acquiring data.")

    st.markdown("### This upload")
    if raw is None:
        st.info("No dataset is loaded. Dataset-specific values, cleaning counts, and findings will appear after upload.")
    else:
        supplied_metadata = [
            ("Source / dataset", source_name),
            ("Source URL", source_url),
            ("Stated study area", dataset_area),
            ("Stated period", dataset_period),
            ("Acquisition date", acquired_on.isoformat() if acquired_on else ""),
            ("Spatial resolution", spatial_resolution),
            ("Temporal resolution", temporal_resolution),
            ("Temperature definition", temperature_definition if temperature_definition != "Not specified" else ""),
            ("Temperature unit", temperature_unit_label if temperature_unit_label != "source unit not documented" else ""),
        ]
        if any(value for _, value in supplied_metadata):
            st.markdown("**User-entered dataset metadata**")
            for label, value in supplied_metadata:
                if value:
                    st.markdown(f"- {label}: {value}")
        else:
            st.warning("No dataset provenance or resolution metadata has been entered. These details remain unverified.")

        if analysis_frame is not None and mapping.get("temperature"):
            stats = summarize_numeric(analysis_frame[derived["temperature"]])
            st.markdown("**Calculated from the selected temperature field**")
            st.write(
                f"{stats['count']:,} usable values; missing {quality.get('temperature_missing', 0):,}; "
                f"invalid {quality.get('temperature_invalid', 0):,}."
            )
            if stats["count"]:
                st.write(
                    f"Mean {stats['mean']:.2f}; median {stats['median']:.2f}; "
                    f"minimum {stats['min']:.2f}; maximum {stats['max']:.2f} "
                    f"({temperature_unit_label})."
                )
        else:
            st.info("No temperature statistics are calculated until a temperature column is selected.")

    st.markdown("### Cleaning methods and statistical methods")
    st.markdown(
        """
        - The uploaded frame is retained as the source. A separate analytical view uses numeric coercion for selected
          measurements, parses dates with the selected day/month convention (timezone-bearing timestamps normalize to UTC),
          and validates latitude/longitude ranges. Invalid derived values become missing;
          original cells remain intact and every row remains in the export.
        - Exact duplicate rows are counted, not removed. Missing and invalid values are reported separately where possible.
        - Mean, median, standard deviation, quartiles, minimum, and maximum use finite numeric observations only.
          Histograms and box plots use the current analysis filters.
        - Date charts show means across the uploaded observations represented on each date. Geographic plots use only
          valid uploaded coordinates. NDVI association uses complete, in-range pairs and Pearson or Spearman correlation.
        - Correlation is descriptive, not causal. Point coverage does not establish citywide representativeness.
        """
    )
    st.markdown("### Assumptions, limitations, and next steps")
    st.markdown(
        """
        - The app cannot independently verify user-entered source metadata, boundaries, measurement definitions, or units.
        - Different heat measures (surface temperature, air temperature, heat index, or hazard indices) must not be
          combined. A Landsat surface-temperature observation is not a direct measure of human heat exposure.
        - Seasonal, spatial, sensor, and observation-time differences can confound comparisons. BHRIGU grids and
          Landsat scenes have different scales and definitions and should not be merged without a documented method.
        - BHRIGU is an interactive explorer; confirm its selected layer and any export options in the portal. For
          Landsat, download a Level-2 scene from EarthExplorer, apply the documented scale factor and fill/quality handling
          before treating stored digital numbers as Kelvin, extract
          the needed pixels in a GIS workflow, and export a CSV with temperatures, dates, coordinates, and any
          spatially and temporally matched vegetation values. This app does not process GeoTIFF rasters.
        - Planned work is limited to analyses enabled by compatible, documented fields in the uploaded dataset.
          Missing vegetation, coordinates, dates, or source metadata prevent those analyses rather than being inferred.
        """
    )
