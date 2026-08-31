import csv
import io
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import streamlit as st

st.set_page_config(
    page_title="EcoFlux Brasil",
    page_icon="🌿",
    layout="wide",
)

# ============================================================
# EcoFlux Brasil — V29
# Arquitetura:
# 1) Dados originais da torre CR3000: 1 min / 30 min / diário
# 2) Eddy Covariance / QC
# 3) Produtos processados: gap-filling, NEE, GPP, Reco, incertezas
# ============================================================

# -----------------------------
# Idioma
# -----------------------------
st.sidebar.title("EcoFlux Brasil")

LANGUAGE = st.sidebar.selectbox(
    "Idioma / Language",
    ["Português", "English"],
    index=0,
    key="language_v29",
)
PT = LANGUAGE == "Português"

def tr(pt, en):
    return pt if PT else en

st.sidebar.caption(
    tr(
        "Interface bilíngue. Nomes de variáveis e unidades da fonte são preservados.",
        "Bilingual interface. Source variable names and units are preserved.",
    )
)

# -----------------------------
# Tabelas sem menu nativo em inglês
# -----------------------------
TABLE_MODE = st.sidebar.radio(
    tr("Tabelas", "Tables"),
    [
        tr("Controles próprios", "Custom controls"),
        tr("Nativa do Streamlit", "Native Streamlit"),
    ],
    index=0,
    key="table_mode_v29",
    help=tr(
        "Controles próprios evitam o menu interno do Streamlit em inglês.",
        "Custom controls avoid Streamlit's native context menu.",
    ),
)
CUSTOM_TABLES = TABLE_MODE == tr("Controles próprios", "Custom controls")

_TABLE_COUNTER = 0

def show_table(data, hide_index=True):
    global _TABLE_COUNTER
    _TABLE_COUNTER += 1
    key = f"table_v29_{_TABLE_COUNTER}"

    if not isinstance(data, pd.DataFrame):
        data = pd.DataFrame(data)

    if not CUSTOM_TABLES:
        st.dataframe(data, use_container_width=True, hide_index=hide_index)
        return

    view = data.copy()

    if len(view.columns):
        with st.expander(tr("Opções da tabela", "Table options"), expanded=False):
            c1, c2, c3 = st.columns([2, 1, 1])
            sort_col = c1.selectbox(
                tr("Ordenar por", "Sort by"),
                ["—"] + list(view.columns),
                key=f"{key}_sort",
            )
            direction = c2.selectbox(
                tr("Ordem", "Order"),
                [tr("Crescente", "Ascending"), tr("Decrescente", "Descending")],
                key=f"{key}_dir",
            )
            rows = c3.selectbox(
                tr("Linhas", "Rows"),
                [25, 50, 100, 250, tr("Todas", "All")],
                index=1,
                key=f"{key}_rows",
            )
            visible = st.multiselect(
                tr("Colunas visíveis", "Visible columns"),
                list(view.columns),
                default=list(view.columns),
                key=f"{key}_cols",
            )

        if visible:
            view = view[visible]
        if sort_col != "—" and sort_col in view.columns:
            asc = direction == tr("Crescente", "Ascending")
            try:
                view = view.sort_values(sort_col, ascending=asc, na_position="last")
            except Exception:
                pass
        if rows != tr("Todas", "All"):
            view = view.head(int(rows))

    st.markdown(
        """
        <style>
        .ecoflux-table {overflow-x:auto;border:1px solid rgba(128,128,128,.25);
                        border-radius:8px;margin-bottom:.8rem}
        .ecoflux-table table {border-collapse:collapse;width:100%;font-size:.93rem}
        .ecoflux-table th,.ecoflux-table td {padding:.45rem .65rem;
                        border-bottom:1px solid rgba(128,128,128,.18);
                        text-align:left;white-space:nowrap}
        .ecoflux-table th {font-weight:600;background:rgba(128,128,128,.08)}
        </style>
        """,
        unsafe_allow_html=True,
    )
    st.markdown(
        '<div class="ecoflux-table">' +
        view.to_html(index=not hide_index, escape=True, border=0) +
        "</div>",
        unsafe_allow_html=True,
    )

# -----------------------------
# Utilidades científicas
# -----------------------------
MISSING_SENTINELS = {-9999, -9999.0}
VARIABLE_PALETTE = [
    "#1f77b4", "#d62728", "#2ca02c", "#9467bd", "#ff7f0e",
    "#17becf", "#8c564b", "#e377c2", "#bcbd22", "#7f7f7f",
    "#393b79", "#637939", "#8c6d31", "#843c39", "#7b4173",
]

QC_CODE_COLORS = {
    0: "#1f77b4",
    1: "#ff7f0e",
    2: "#2ca02c",
    3: "#d62728",
    4: "#9467bd",
}

FOKEN_CLASS_COLORS = {
    "Alta qualidade": "#2ca02c",
    "Qualidade moderada": "#ff7f0e",
    "Baixa qualidade": "#d62728",
    "Fora da escala selecionada": "#7f7f7f",
}

TEMPORAL_FIELDS = {
    "timestamp", "date", "time", "datetime", "datatime",
    "record", "doy", "day_of_year", "year", "month", "day", "hour",
}

GAPFILL_FAMILIES = ["NEE", "LE", "H", "Rg", "VPD", "rH", "Tair", "Tsoil"]

SCIENTIFIC_GROUPS = {
    "Ventos e Turbulência": [
        "WS", "WindDir", "u", "v", "w", "ustar", "u*", "TKE", "sonic", "Tau"
    ],
    "Fluxos de Energia e Massa": [
        "H", "LE", "Fc", "co2_flux", "h2o_flux", "Tau", "NEE", "Reco", "GPP"
    ],
    "Balanço de Radiação": [
        "Rg_i", "Rg_r", "Rg", "SW_IN", "SW_OUT", "LW_IN", "LW_OUT", "NET",
        "Rn", "PAR", "PPFD"
    ],
    "Variáveis Bioclimáticas e de Solo": [
        "T_ar", "Tair", "AirTC", "UR_ar", "RH", "rH", "VPD", "PA", "P",
        "T_solo", "Tsoil", "VW_", "SWC", "VWC", "PPT", "G"
    ],
    "Diagnósticos e Controle de Qualidade": [
        "qc_", "_qc", "_fqc", "diag", "footprint"
    ],
}

def variable_color(var):
    idx = sum((i + 1) * ord(ch) for i, ch in enumerate(str(var))) % len(VARIABLE_PALETTE)
    return VARIABLE_PALETTE[idx]

def qc_color(code):
    try:
        return QC_CODE_COLORS.get(int(float(code)), "#7f7f7f")
    except Exception:
        return "#7f7f7f"

def is_qc(name):
    n = str(name).lower()
    return n.startswith("qc_") or "_qc" in n or "_fqc" in n or n.endswith("_qc")

def scientific_group(name):
    n = str(name)
    low = n.lower()
    if low in TEMPORAL_FIELDS:
        return "Temporal e Identificação"
    if is_qc(n):
        return "Diagnósticos e Controle de Qualidade"

    # ordem deliberada para evitar classificar GPP como G (solo)
    for group in [
        "Fluxos de Energia e Massa",
        "Balanço de Radiação",
        "Ventos e Turbulência",
        "Variáveis Bioclimáticas e de Solo",
        "Diagnósticos e Controle de Qualidade",
    ]:
        for token in SCIENTIFIC_GROUPS[group]:
            if token.lower() in low:
                return group
    return "Outras Variáveis / Produtos Derivados"

def clean_numeric(series):
    s = pd.to_numeric(series, errors="coerce")
    return s.mask(s.isin(MISSING_SENTINELS))

def unit_label(var, units):
    u = units.get(var, "")
    return f"{var} [{u}]" if str(u).strip() else str(var)

def unit_only(var, units):
    u = str(units.get(var, "")).strip()
    return u if u else tr("unidade não informada", "unit not reported")

def resolution_label(value):
    if PT:
        return value
    return {
        "1 min": "1 min",
        "30 min": "30 min",
        "Horário": "Hourly",
        "Diário": "Daily",
        "Semanal": "Weekly",
        "Mensal": "Monthly",
    }.get(value, value)

def temporal_hover_text(ts, resolution):
    ts = pd.Timestamp(ts)
    if resolution == "1 min":
        return ts.strftime("%d/%m/%Y %H:%M")
    if resolution == "30 min":
        return ts.strftime("%d/%m/%Y %H:%M")
    if resolution == "Horário":
        return ts.strftime("%d/%m/%Y %H:00")
    if resolution == "Diário":
        return ts.strftime("%d/%m/%Y")
    if resolution == "Semanal":
        end = ts.normalize()
        start = end - pd.Timedelta(days=6)
        return f"{start:%d/%m/%Y} – {end:%d/%m/%Y}"
    if resolution == "Mensal":
        months_pt = [
            "Janeiro","Fevereiro","Março","Abril","Maio","Junho",
            "Julho","Agosto","Setembro","Outubro","Novembro","Dezembro"
        ]
        months_en = [
            "January","February","March","April","May","June",
            "July","August","September","October","November","December"
        ]
        months = months_pt if PT else months_en
        return f"{months[ts.month-1]}/{ts.year}"
    return ts.strftime("%d/%m/%Y %H:%M")

def temporal_axis_title(resolution):
    return tr(
        {
            "1 min": "Data e hora",
            "30 min": "Data e hora",
            "Horário": "Data e hora",
            "Diário": "Data",
            "Semanal": "Período semanal",
            "Mensal": "Mês",
        }.get(resolution, "Data e hora"),
        {
            "1 min": "Date and time",
            "30 min": "Date and time",
            "Horário": "Date and time",
            "Diário": "Date",
            "Semanal": "Weekly period",
            "Mensal": "Month",
        }.get(resolution, "Date and time"),
    )

def period_controls(prefix, start, end):
    c1, c2, c3, c4 = st.columns(4)
    d1 = c1.date_input(tr("Data inicial", "Start date"), start.date(), key=f"{prefix}_d1")
    t1 = c2.time_input(tr("Hora inicial", "Start time"), start.time(), key=f"{prefix}_t1")
    d2 = c3.date_input(tr("Data final", "End date"), end.date(), key=f"{prefix}_d2")
    t2 = c4.time_input(tr("Hora final", "End time"), end.time(), key=f"{prefix}_t2")
    return pd.Timestamp.combine(d1, t1), pd.Timestamp.combine(d2, t2)

def filter_period(df, start, end):
    return df[(df["TIMESTAMP"] >= start) & (df["TIMESTAMP"] <= end)].copy()

def aggregate_numeric(df, vars_, resolution):
    d = df[["TIMESTAMP"] + vars_].copy().set_index("TIMESTAMP")
    if resolution in {"1 min", "30 min"}:
        return d.reset_index()
    rule = {
        "Horário": "1h",
        "Diário": "1D",
        "Semanal": "1W",
        "Mensal": "1MS",
    }[resolution]
    return d.resample(rule).mean(numeric_only=True).reset_index()

def expected_timedelta(source_key):
    return {
        "1 min": pd.Timedelta(minutes=1),
        "30 min": pd.Timedelta(minutes=30),
        "Diário": pd.Timedelta(days=1),
    }.get(source_key)

def gap_table(df, expected):
    if df is None or df.empty or expected is None:
        return pd.DataFrame()
    d = df[["TIMESTAMP"]].dropna().sort_values("TIMESTAMP").copy()
    d["diff"] = d["TIMESTAMP"].diff()
    gaps = d[d["diff"] > expected * 1.5].copy()
    rows = []
    for idx, row in gaps.iterrows():
        current = row["TIMESTAMP"]
        previous = d.loc[d.index[d.index.get_loc(idx)-1], "TIMESTAMP"]
        missing_est = max(int(round(row["diff"] / expected)) - 1, 0)
        rows.append({
            tr("Último registro antes da lacuna", "Last record before gap"): previous,
            tr("Primeiro registro após a lacuna", "First record after gap"): current,
            tr("Duração", "Duration"): str(row["diff"]),
            tr("Registros esperados ausentes", "Estimated missing records"): missing_est,
        })
    return pd.DataFrame(rows)

def add_gap_breaks(x, y, expected):
    if expected is None or len(x) == 0:
        return list(x), list(y)

    xs, ys = [], []
    prev = None
    for ts, val in zip(x, y):
        ts = pd.Timestamp(ts)
        if prev is not None and ts - prev > expected * 1.5:
            xs.append(prev + expected)
            ys.append(None)
        xs.append(ts)
        ys.append(None if pd.isna(val) else val)
        prev = ts
    return xs, ys

def line_plot(data, vars_, units, title, start, end, resolution, source_expected=None):
    fig = go.Figure()
    colors = {v: variable_color(v) for v in vars_}

    for v in vars_:
        values = pd.to_numeric(data[v], errors="coerce")
        x = data["TIMESTAMP"]

        if resolution in {"1 min", "30 min"} and source_expected is not None:
            pxs, pys = add_gap_breaks(x, values, source_expected)
            hover = [
                temporal_hover_text(ts, resolution) if ts is not None else ""
                for ts in pxs
            ]
            custom = np.column_stack([
                np.array(hover, dtype=object),
                np.array([unit_only(v, units)] * len(pxs), dtype=object),
            ])
            fig.add_trace(go.Scattergl(
                x=pxs, y=pys, mode="lines",
                name=unit_label(v, units),
                line=dict(color=colors[v], width=1.8),
                connectgaps=False,
                customdata=custom,
                hovertemplate=(
                    "<b>%{customdata[0]}</b><br>"
                    + str(v) + ": %{y:.6g} %{customdata[1]}<extra></extra>"
                ),
            ))
        else:
            hover = [temporal_hover_text(ts, resolution) for ts in x]
            custom = np.column_stack([
                np.array(hover, dtype=object),
                np.array([unit_only(v, units)] * len(data), dtype=object),
            ])
            fig.add_trace(go.Scattergl(
                x=x, y=values, mode="lines",
                name=unit_label(v, units),
                line=dict(color=colors[v], width=1.8),
                connectgaps=False,
                customdata=custom,
                hovertemplate=(
                    "<b>%{customdata[0]}</b><br>"
                    + str(v) + ": %{y:.6g} %{customdata[1]}<extra></extra>"
                ),
            ))

    fig.update_layout(
        title=title,
        xaxis_title=temporal_axis_title(resolution),
        yaxis_title=tr("Valor", "Value"),
        hovermode="x unified",
        height=480,
        margin=dict(l=20, r=20, t=55, b=20),
    )
    fig.update_xaxes(range=[start, end])
    st.plotly_chart(fig, use_container_width=True)

def stats_table(df, vars_, units):
    rows = []
    for v in vars_:
        s = pd.to_numeric(df[v], errors="coerce")
        rows.append({
            tr("Variável", "Variable"): v,
            tr("Unidade", "Unit"): unit_only(v, units),
            tr("N disponível", "N available"): int(s.notna().sum()),
            tr("Disponibilidade (%)", "Availability (%)"): round(100*s.notna().mean(), 2) if len(s) else np.nan,
            tr("Média", "Mean"): s.mean(),
            tr("Mediana", "Median"): s.median(),
            tr("Desvio-padrão", "Standard deviation"): s.std(),
            tr("Mínimo", "Minimum"): s.min(),
            tr("Máximo", "Maximum"): s.max(),
        })
    show_table(pd.DataFrame(rows))

def comparison_mode_label(value):
    if PT:
        return value
    return {
        "Gráficos separados": "Separate charts",
        "Mesmo gráfico — valores originais": "Same chart — original values",
        "Dois eixos Y": "Two Y axes",
        "Normalizado (z-score)": "Normalized (z-score)",
    }.get(value, value)

def plot_two_y_axes(data, vars_, units, start, end, resolution):
    fig = go.Figure()
    hover = [temporal_hover_text(ts, resolution) for ts in data["TIMESTAMP"]]
    for i, v in enumerate(vars_):
        fig.add_trace(go.Scattergl(
            x=data["TIMESTAMP"],
            y=data[v],
            mode="lines",
            name=unit_label(v, units),
            line=dict(color=variable_color(v), width=1.8),
            yaxis="y" if i % 2 == 0 else "y2",
            customdata=np.array(hover, dtype=object).reshape(-1, 1),
            hovertemplate=(
                "<b>%{customdata[0]}</b><br>" + str(v) +
                ": %{y:.6g} " + unit_only(v, units) + "<extra></extra>"
            ),
        ))
    left = [v for i, v in enumerate(vars_) if i % 2 == 0]
    right = [v for i, v in enumerate(vars_) if i % 2 == 1]
    fig.update_layout(
        title=tr("Comparação com dois eixos Y", "Comparison with two Y axes"),
        xaxis_title=temporal_axis_title(resolution),
        yaxis=dict(title=", ".join(left)),
        yaxis2=dict(title=", ".join(right), overlaying="y", side="right"),
        hovermode="x unified",
        height=500,
    )
    fig.update_xaxes(range=[start, end])
    st.plotly_chart(fig, use_container_width=True)

def plot_zscore(data, vars_, start, end, resolution):
    fig = go.Figure()
    hover = [temporal_hover_text(ts, resolution) for ts in data["TIMESTAMP"]]
    for v in vars_:
        s = pd.to_numeric(data[v], errors="coerce")
        sd = s.std()
        z = (s - s.mean()) / sd if pd.notna(sd) and sd != 0 else s*np.nan
        fig.add_trace(go.Scattergl(
            x=data["TIMESTAMP"], y=z, mode="lines",
            name=v,
            line=dict(color=variable_color(v), width=1.8),
            customdata=np.array(hover, dtype=object).reshape(-1, 1),
            hovertemplate="<b>%{customdata[0]}</b><br>"+str(v)+": %{y:.3f} z<extra></extra>",
        ))
    fig.update_layout(
        title=tr("Comparação normalizada (z-score)", "Normalized comparison (z-score)"),
        xaxis_title=temporal_axis_title(resolution),
        yaxis_title="z-score",
        hovermode="x unified",
        height=500,
    )
    fig.update_xaxes(range=[start, end])
    st.plotly_chart(fig, use_container_width=True)

# ============================================================
# Leitura Campbell TOA5
# ============================================================

def _uploaded_bytes(uploaded_file):
    if hasattr(uploaded_file, "getvalue"):
        return uploaded_file.getvalue()
    return uploaded_file.read()

@st.cache_data(show_spinner=False)
def parse_toa5_bytes(file_bytes, filename="arquivo.dat"):
    text = file_bytes.decode("utf-8", errors="replace")
    lines = text.splitlines()
    if len(lines) < 5:
        raise ValueError("Arquivo TOA5 incompleto.")

    meta = next(csv.reader([lines[0]]))
    headers = next(csv.reader([lines[1]]))
    units_row = next(csv.reader([lines[2]]))
    proc_row = next(csv.reader([lines[3]]))

    if not meta or meta[0] != "TOA5":
        raise ValueError("O arquivo não foi reconhecido como Campbell Scientific TOA5.")

    df = pd.read_csv(
        io.StringIO(text),
        skiprows=4,
        names=headers,
        na_values=["NAN", "NaN", "-9999"],
        low_memory=False,
    )

    if "TIMESTAMP" not in df.columns:
        raise ValueError("Coluna TIMESTAMP não encontrada.")

    df["TIMESTAMP"] = pd.to_datetime(df["TIMESTAMP"], errors="coerce")
    df = df[df["TIMESTAMP"].notna()].sort_values("TIMESTAMP").reset_index(drop=True)

    # Preservar colunas temporais auxiliares como texto; converter o restante quando possível.
    for c in df.columns:
        if c == "TIMESTAMP":
            continue
        if c.endswith("_TMx") or c.endswith("_TMn"):
            continue
        numeric = pd.to_numeric(df[c], errors="coerce")
        if numeric.notna().sum() > 0:
            df[c] = numeric.mask(numeric.isin(MISSING_SENTINELS))

    units = {
        h: str(u).strip()
        for h, u in zip(headers, units_row)
        if str(u).strip()
    }
    processing = {
        h: str(p).strip()
        for h, p in zip(headers, proc_row)
        if str(p).strip()
    }

    table_name = meta[-1] if meta else filename
    return df, units, processing, meta, table_name

def identify_toa5_resolution(table_name, filename):
    text = f"{table_name} {filename}".lower()
    if "1min" in text or "1_min" in text:
        return "1 min"
    if "30min" in text or "30_min" in text:
        return "30 min"
    if "diario" in text or "daily" in text:
        return "Diário"
    return table_name

# ============================================================
# Leitura XLSX processado
# ============================================================

@st.cache_data(show_spinner=False)
def load_processed_xlsx(file_bytes):
    bio = io.BytesIO(file_bytes)
    xls = pd.ExcelFile(bio)
    sheet = "output" if "output" in xls.sheet_names else xls.sheet_names[0]

    bio.seek(0)
    meta = pd.read_excel(bio, sheet_name=sheet, header=None, nrows=2)
    headers = [str(x).strip() for x in meta.iloc[0].tolist()]
    raw_units = meta.iloc[1].tolist()
    units = {
        h: str(u).strip()
        for h, u in zip(headers, raw_units)
        if pd.notna(u) and str(u).strip() not in {"", "-", "nan"}
    }

    bio.seek(0)
    df = pd.read_excel(bio, sheet_name=sheet, header=0, skiprows=[1]).copy()

    time_candidates = [
        c for c in df.columns
        if str(c).strip().lower() in {"date time","datetime","date_time","datatime","timestamp"}
    ]
    if not time_candidates:
        raise ValueError("Coluna temporal não encontrada na planilha processada.")

    tc = time_candidates[0]
    df["TIMESTAMP"] = pd.to_datetime(df[tc], errors="coerce")
    df = df[df["TIMESTAMP"].notna()].sort_values("TIMESTAMP").reset_index(drop=True)

    for c in df.columns:
        if c in {tc, "TIMESTAMP"}:
            continue
        num = pd.to_numeric(df[c], errors="coerce")
        if num.notna().sum() > 0:
            df[c] = num.mask(num.isin(MISSING_SENTINELS))

    return df, units, sheet

# ============================================================
# Uploads
# ============================================================

st.sidebar.subheader(tr("Fontes de dados", "Data sources"))

tower_files = st.sidebar.file_uploader(
    tr("Dados originais CR3000 (.dat)", "Original CR3000 data (.dat)"),
    type=["dat"],
    accept_multiple_files=True,
    key="tower_dat_v29",
    help=tr(
        "Carregue os arquivos TOA5 de 1 min, 30 min e diário. O EcoFlux reconhece cada resolução automaticamente.",
        "Upload TOA5 1-min, 30-min and daily files. EcoFlux identifies each resolution automatically.",
    ),
)

processed_file = st.sidebar.file_uploader(
    tr("Produtos processados (.xlsx) — opcional", "Processed products (.xlsx) — optional"),
    type=["xlsx"],
    key="processed_xlsx_v29",
)

tower_sources = {}
tower_meta = {}

for f in tower_files or []:
    try:
        data, units, processing, meta, table_name = parse_toa5_bytes(
            _uploaded_bytes(f), f.name
        )
        res = identify_toa5_resolution(table_name, f.name)
        tower_sources[res] = {
            "df": data,
            "units": units,
            "processing": processing,
            "table_name": table_name,
            "filename": f.name,
        }
        tower_meta[res] = meta
    except Exception as exc:
        st.sidebar.error(f"{f.name}: {exc}")

processed = None
if processed_file is not None:
    try:
        pdf, punits, psheet = load_processed_xlsx(_uploaded_bytes(processed_file))
        processed = {"df": pdf, "units": punits, "sheet": psheet}
    except Exception as exc:
        st.sidebar.error(tr(
            f"Erro no XLSX processado: {exc}",
            f"Processed XLSX error: {exc}",
        ))

if not tower_sources and processed is None:
    st.title("EcoFlux Brasil")
    st.info(
        tr(
            "Carregue os arquivos CR3000 da torre e, opcionalmente, a planilha de produtos processados.",
            "Upload the CR3000 tower files and, optionally, the processed-products workbook.",
        )
    )
    st.stop()

# ============================================================
# Navegação
# ============================================================

pages = {
    "overview": tr("Visão Geral", "Overview"),
    "tower": tr("Dados Originais da Torre", "Original Tower Data"),
    "structure": tr("Estrutura Científica", "Scientific Structure"),
    "compare": tr("Comparar Variáveis", "Compare Variables"),
    "gapfill": tr("Preenchimento de Lacunas", "Gap Filling"),
    "carbon": tr("Balanço de Carbono", "Carbon Balance"),
    "qc": tr("Qualidade dos Dados", "Data Quality"),
    "about": tr("Sobre os Dados", "About the Data"),
    "request": tr("Solicitar Dados", "Request Data"),
}

page = st.sidebar.radio(tr("Navegação", "Navigation"), list(pages.values()))
page_key = next(k for k, v in pages.items() if v == page)

# ============================================================
# Visão Geral
# ============================================================

if page_key == "overview":
    st.title("EcoFlux Brasil")
    st.subheader(tr("Arquitetura atual das fontes", "Current data-source architecture"))

    cards = []
    order = ["1 min", "30 min", "Diário"]
    for res in order:
        if res in tower_sources:
            d = tower_sources[res]["df"]
            cards.append({
                tr("Camada", "Layer"): tr("Dados originais da torre", "Original tower data"),
                tr("Fonte", "Source"): tower_sources[res]["table_name"],
                tr("Resolução", "Resolution"): resolution_label(res),
                tr("Registros", "Records"): len(d),
                tr("Início", "Start"): d["TIMESTAMP"].min().strftime("%d/%m/%Y %H:%M"),
                tr("Fim", "End"): d["TIMESTAMP"].max().strftime("%d/%m/%Y %H:%M"),
            })

    if processed is not None:
        d = processed["df"]
        cards.append({
            tr("Camada", "Layer"): tr("Produtos processados", "Processed products"),
            tr("Fonte", "Source"): processed["sheet"],
            tr("Resolução", "Resolution"): "30 min / produtos",
            tr("Registros", "Records"): len(d),
            tr("Início", "Start"): d["TIMESTAMP"].min().strftime("%d/%m/%Y %H:%M"),
            tr("Fim", "End"): d["TIMESTAMP"].max().strftime("%d/%m/%Y %H:%M"),
        })

    show_table(pd.DataFrame(cards))

    if "30 min" in tower_sources:
        d = tower_sources["30 min"]["df"]
        gaps = gap_table(d, expected_timedelta("30 min"))
        st.subheader(tr(
            "Continuidade temporal — série de 30 minutos",
            "Temporal continuity — 30-minute series",
        ))
        if gaps.empty:
            st.success(tr(
                "Nenhuma lacuna temporal relevante foi detectada.",
                "No relevant temporal gaps were detected.",
            ))
        else:
            st.warning(tr(
                f"Foram detectadas {len(gaps)} lacuna(s) real(is) na aquisição. "
                "Os gráficos não conectam linhas através desses intervalos.",
                f"{len(gaps)} real acquisition gap(s) were detected. "
                "Plots do not connect lines across these intervals.",
            ))
            show_table(gaps)

    st.info(tr(
        "Os arquivos CR3000 representam a camada observacional original da torre. "
        "Produtos como NEE, GPP, Reco e séries preenchidas permanecem em uma camada separada.",
        "CR3000 files represent the tower's original observational layer. "
        "Products such as NEE, GPP, Reco and gap-filled series remain in a separate layer.",
    ))

# ============================================================
# Dados Originais da Torre
# ============================================================

elif page_key == "tower":
    st.header(tr("Dados Originais da Torre", "Original Tower Data"))

    source_order = [x for x in ["1 min", "30 min", "Diário"] if x in tower_sources]
    if not source_order:
        st.info(tr("Nenhum arquivo CR3000 carregado.", "No CR3000 file loaded."))
        st.stop()

    source = st.selectbox(
        tr("Resolução observacional", "Observational resolution"),
        source_order,
        format_func=resolution_label,
        key="tower_source_v29",
    )

    src = tower_sources[source]
    df = src["df"]
    units = src["units"]
    expected = expected_timedelta(source)

    numeric_vars = [
        c for c in df.columns
        if c not in {"TIMESTAMP", "RECORD"} and pd.api.types.is_numeric_dtype(df[c])
    ]
    groups = {}
    for c in numeric_vars:
        groups.setdefault(scientific_group(c), []).append(c)

    group = st.selectbox(
        tr("Grupo científico", "Scientific group"),
        list(groups.keys()),
        key="tower_group_v29",
    )
    var = st.selectbox(
        tr("Variável", "Variable"),
        groups[group],
        format_func=lambda x: unit_label(x, units),
        key="tower_var_v29",
    )

    full_start = df["TIMESTAMP"].min()
    full_end = df["TIMESTAMP"].max()
    start, end = period_controls("tower_v29", full_start, full_end)

    resolution_options = {
        "1 min": ["1 min", "30 min", "Horário", "Diário", "Semanal", "Mensal"],
        "30 min": ["30 min", "Horário", "Diário", "Semanal", "Mensal"],
        "Diário": ["Diário", "Semanal", "Mensal"],
    }[source]

    agg_res = st.selectbox(
        tr("Resolução do gráfico", "Plot resolution"),
        resolution_options,
        format_func=resolution_label,
        key="tower_plot_res_v29",
    )

    if start > end:
        st.error(tr("Período inválido.", "Invalid period."))
    else:
        sub = filter_period(df, start, end)
        data = aggregate_numeric(sub, [var], agg_res)
        line_plot(
            data, [var], units,
            unit_label(var, units),
            start, end, agg_res,
            source_expected=expected if agg_res in {"1 min","30 min"} else None,
        )
        stats_table(sub, [var], units)

        gaps = gap_table(sub, expected)
        if not gaps.empty:
            st.subheader(tr("Lacunas no período selecionado", "Gaps in selected period"))
            show_table(gaps)

# ============================================================
# Estrutura Científica
# ============================================================

elif page_key == "structure":
    st.header(tr("Estrutura Científica", "Scientific Structure"))
    st.write(tr(
        "As variáveis são organizadas segundo a estrutura típica de uma torre micrometeorológica. "
        "As unidades exibidas vêm dos próprios arquivos TOA5 ou da planilha processada.",
        "Variables are organized according to a typical micrometeorological tower structure. "
        "Displayed units come from the TOA5 files or the processed workbook.",
    ))

    rows = []
    for res, src in tower_sources.items():
        df = src["df"]
        for c in df.columns:
            if c == "TIMESTAMP":
                continue
            rows.append({
                tr("Fonte", "Source"): src["table_name"],
                tr("Resolução", "Resolution"): resolution_label(res),
                tr("Grupo", "Group"): scientific_group(c),
                tr("Variável", "Variable"): c,
                tr("Unidade", "Unit"): src["units"].get(c, ""),
                tr("Processamento Campbell", "Campbell processing"): src["processing"].get(c, ""),
            })

    if processed is not None:
        for c in processed["df"].columns:
            if c == "TIMESTAMP":
                continue
            rows.append({
                tr("Fonte", "Source"): tr("Produtos processados", "Processed products"),
                tr("Resolução", "Resolution"): "30 min / produtos",
                tr("Grupo", "Group"): scientific_group(c),
                tr("Variável", "Variable"): c,
                tr("Unidade", "Unit"): processed["units"].get(c, ""),
                tr("Processamento Campbell", "Campbell processing"): "",
            })

    show_table(pd.DataFrame(rows))

# ============================================================
# Comparar Variáveis
# ============================================================

elif page_key == "compare":
    st.header(tr("Comparar Variáveis", "Compare Variables"))

    source_choices = [resolution_label(x) for x in ["1 min","30 min","Diário"] if x in tower_sources]
    source_keys = [x for x in ["1 min","30 min","Diário"] if x in tower_sources]

    if processed is not None:
        source_choices.append(tr("Produtos processados", "Processed products"))
        source_keys.append("processed")

    source_display = st.selectbox(
        tr("Fonte para comparação", "Comparison source"),
        source_choices,
        key="compare_source_v29",
    )
    source_key = source_keys[source_choices.index(source_display)]

    if source_key == "processed":
        df = processed["df"]
        units = processed["units"]
        default_resolution = "Diário"
        resolutions = ["30 min","Horário","Diário","Semanal","Mensal"]
        expected = pd.Timedelta(minutes=30)
    else:
        src = tower_sources[source_key]
        df = src["df"]
        units = src["units"]
        expected = expected_timedelta(source_key)
        if source_key == "1 min":
            resolutions = ["1 min","30 min","Horário","Diário","Semanal","Mensal"]
        elif source_key == "30 min":
            resolutions = ["30 min","Horário","Diário","Semanal","Mensal"]
        else:
            resolutions = ["Diário","Semanal","Mensal"]
        default_resolution = "Diário"

    vars_all = [
        c for c in df.columns
        if c not in {"TIMESTAMP","RECORD"} and
        pd.api.types.is_numeric_dtype(df[c]) and
        not is_qc(c)
    ]

    vars_ = st.multiselect(
        tr("Variáveis", "Variables"),
        vars_all,
        format_func=lambda x: unit_label(x, units),
        key="compare_vars_v29",
    )

    start, end = period_controls(
        "compare_v29",
        df["TIMESTAMP"].min(),
        df["TIMESTAMP"].max(),
    )

    c1, c2 = st.columns(2)
    resolution = c1.selectbox(
        tr("Resolução", "Resolution"),
        resolutions,
        index=resolutions.index(default_resolution) if default_resolution in resolutions else 0,
        format_func=resolution_label,
        key="compare_resolution_v29",
    )
    mode = c2.selectbox(
        tr("Forma de visualização", "Visualization mode"),
        [
            "Gráficos separados",
            "Mesmo gráfico — valores originais",
            "Dois eixos Y",
            "Normalizado (z-score)",
        ],
        format_func=comparison_mode_label,
        key="compare_mode_v29",
    )

    if len(vars_) < 2:
        st.info(tr("Selecione pelo menos duas variáveis.", "Select at least two variables."))
    elif start > end:
        st.error(tr("Período inválido.", "Invalid period."))
    else:
        sub = filter_period(df, start, end)
        data = aggregate_numeric(sub, vars_, resolution)

        if mode == "Gráficos separados":
            for v in vars_:
                line_plot(
                    data[["TIMESTAMP", v]],
                    [v], units, unit_label(v, units),
                    start, end, resolution,
                    source_expected=expected if resolution in {"1 min","30 min"} else None,
                )
        elif mode == "Mesmo gráfico — valores originais":
            line_plot(
                data, vars_, units,
                tr("Comparação de variáveis", "Variable comparison"),
                start, end, resolution,
                source_expected=expected if resolution in {"1 min","30 min"} else None,
            )
        elif mode == "Dois eixos Y":
            plot_two_y_axes(data, vars_, units, start, end, resolution)
        else:
            plot_zscore(data, vars_, start, end, resolution)

        st.subheader(tr("Estatísticas", "Statistics"))
        stats_table(sub, vars_, units)

        corr = data[vars_].corr(method="pearson", min_periods=3)
        st.subheader(tr("Correlação de Pearson", "Pearson correlation"))
        fig = px.imshow(corr, text_auto=".2f", aspect="auto", zmin=-1, zmax=1)
        st.plotly_chart(fig, use_container_width=True)
        st.caption(tr("Correlação não implica causalidade.", "Correlation does not imply causation."))

# ============================================================
# Preenchimento de Lacunas
# ============================================================

elif page_key == "gapfill":
    st.header(tr("Preenchimento de Lacunas", "Gap Filling"))

    if processed is None:
        st.info(tr(
            "Carregue a planilha de produtos processados para comparar séries observadas e preenchidas.",
            "Upload the processed-products workbook to compare observed and gap-filled series.",
        ))
    else:
        df = processed["df"]
        units = processed["units"]
        available = [
            b for b in GAPFILL_FAMILIES
            if f"{b}_orig" in df.columns and f"{b}_f" in df.columns
        ]
        if not available:
            st.info(tr("Nenhuma família _orig/_f encontrada.", "No _orig/_f family found."))
        else:
            base = st.selectbox(tr("Família", "Family"), available, key="gap_family_v29")
            start, end = period_controls(
                "gap_v29", df["TIMESTAMP"].min(), df["TIMESTAMP"].max()
            )
            res = st.selectbox(
                tr("Resolução", "Resolution"),
                ["30 min","Horário","Diário","Semanal","Mensal"],
                format_func=resolution_label,
                key="gap_res_v29",
            )

            if start <= end:
                sub = filter_period(df, start, end)
                orig = f"{base}_orig"
                filled = f"{base}_f"
                data = aggregate_numeric(sub, [orig, filled], res)
                line_plot(
                    data, [orig, filled], units,
                    tr(f"{base}: observado × preenchido", f"{base}: observed × gap-filled"),
                    start, end, res,
                    source_expected=pd.Timedelta(minutes=30) if res=="30 min" else None,
                )

                a = pd.to_numeric(sub[orig], errors="coerce")
                b = pd.to_numeric(sub[filled], errors="coerce")
                status = pd.Series(np.select(
                    [a.notna(), a.isna() & b.notna(), b.isna()],
                    [tr("Observado","Observed"), tr("Preenchido","Gap-filled"), tr("Ausente","Missing")],
                    default=tr("Ausente","Missing"),
                ))
                vc = status.value_counts()
                rows = []
                for label in [
                    tr("Observado","Observed"),
                    tr("Preenchido","Gap-filled"),
                    tr("Ausente","Missing"),
                ]:
                    n = int(vc.get(label, 0))
                    rows.append({
                        tr("Situação","Status"): label,
                        tr("Registros","Records"): n,
                        tr("Percentual (%)","Percentage (%)"): round(100*n/len(status),2) if len(status) else 0,
                    })
                show_table(pd.DataFrame(rows))

# ============================================================
# Balanço de Carbono
# ============================================================

elif page_key == "carbon":
    st.header(tr("Balanço de Carbono", "Carbon Balance"))

    if processed is None:
        st.info(tr(
            "Carregue a planilha de produtos processados para acessar NEE, GPP e Reco.",
            "Upload the processed-products workbook to access NEE, GPP and Reco.",
        ))
    else:
        df = processed["df"]
        units = processed["units"]
        candidates = [
            c for c in [
                "NEE", "NEE_orig", "NEE_f", "NEE_fall",
                "Reco", "Reco_DT", "GPP_f", "GPP_DT",
                "NEE_U05_f", "NEE_U50_f", "NEE_U95_f"
            ]
            if c in df.columns
        ]
        selected = st.multiselect(
            tr("Produtos de carbono", "Carbon products"),
            candidates,
            default=[c for c in ["NEE_f","Reco","GPP_f"] if c in candidates],
            format_func=lambda x: unit_label(x, units),
            key="carbon_vars_v29",
        )
        start, end = period_controls(
            "carbon_v29", df["TIMESTAMP"].min(), df["TIMESTAMP"].max()
        )
        res = st.selectbox(
            tr("Resolução", "Resolution"),
            ["30 min","Horário","Diário","Semanal","Mensal"],
            index=2,
            format_func=resolution_label,
            key="carbon_res_v29",
        )

        if selected and start <= end:
            sub = filter_period(df, start, end)
            data = aggregate_numeric(sub, selected, res)
            line_plot(
                data, selected, units,
                tr("Produtos de carbono", "Carbon products"),
                start, end, res,
                source_expected=pd.Timedelta(minutes=30) if res=="30 min" else None,
            )
            stats_table(sub, selected, units)

# ============================================================
# Qualidade dos Dados
# ============================================================

elif page_key == "qc":
    st.header(tr("Qualidade dos Dados", "Data Quality"))

    if processed is None:
        st.info(tr(
            "A camada QC de Eddy Covariance depende da planilha de produtos processados.",
            "The Eddy Covariance QC layer requires the processed-products workbook.",
        ))
    else:
        df = processed["df"]
        qc_vars = [
            c for c in df.columns
            if is_qc(c) and pd.api.types.is_numeric_dtype(df[c])
        ]

        st.markdown(tr(
            """
**Referência de Foken:** o controle de qualidade clássico em Eddy Covariance combina testes
de estacionariedade e características integrais da turbulência (ITC). A comparação abaixo
não redefine automaticamente o significado original de uma coluna `_fqc` ou `_qc`.
""",
            """
**Foken reference:** classic Eddy Covariance quality control combines stationarity and
integral turbulence characteristics (ITC) tests. The comparison below does not automatically
redefine the original meaning of an `_fqc` or `_qc` field.
"""
        ))

        foken_ref = pd.DataFrame([
            {
                tr("Classe resumida","Summary class"): 0,
                tr("Escala estendida","Extended scale"): "1–3",
                tr("Qualidade","Quality"): tr("Alta qualidade","High quality"),
                tr("Uso típico","Typical use"): tr(
                    "Fluxos diretos e análises científicas, conforme protocolo.",
                    "Direct fluxes and scientific analyses, subject to protocol.",
                ),
            },
            {
                tr("Classe resumida","Summary class"): 1,
                tr("Escala estendida","Extended scale"): "4–6",
                tr("Qualidade","Quality"): tr("Qualidade moderada","Moderate quality"),
                tr("Uso típico","Typical use"): tr(
                    "Integrações e balanços com cautela.",
                    "Integrations and balances with caution.",
                ),
            },
            {
                tr("Classe resumida","Summary class"): 2,
                tr("Escala estendida","Extended scale"): "7–9",
                tr("Qualidade","Quality"): tr("Baixa qualidade","Low quality"),
                tr("Uso típico","Typical use"): tr(
                    "Geralmente rejeitada quando o protocolo exige alta qualidade.",
                    "Usually rejected when the protocol requires high quality.",
                ),
            },
        ])
        show_table(foken_ref)

        if not qc_vars:
            st.info(tr("Nenhuma coluna QC encontrada.", "No QC column found."))
        else:
            qc = st.selectbox(tr("Indicador QC","QC indicator"), qc_vars, key="qc_var_v29")
            start, end = period_controls(
                "qc_v29", df["TIMESTAMP"].min(), df["TIMESTAMP"].max()
            )
            scale = st.selectbox(
                tr("Escala de comparação","Comparison scale"),
                [
                    "Foken — 3 classes (0, 1, 2)",
                    "Foken — escala estendida (1–9)",
                ],
                key="qc_scale_v29",
            )

            def classify(v):
                if pd.isna(v):
                    return None
                try:
                    x = int(float(v))
                except Exception:
                    return "Fora da escala selecionada"
                if scale.startswith("Foken — 3"):
                    return {
                        0:"Alta qualidade",
                        1:"Qualidade moderada",
                        2:"Baixa qualidade",
                    }.get(x,"Fora da escala selecionada")
                if 1 <= x <= 3:
                    return "Alta qualidade"
                if 4 <= x <= 6:
                    return "Qualidade moderada"
                if 7 <= x <= 9:
                    return "Baixa qualidade"
                return "Fora da escala selecionada"

            if start <= end:
                sub = filter_period(df,start,end)
                s = pd.to_numeric(sub[qc],errors="coerce").dropna()
                counts = s.value_counts().sort_index()
                total = int(counts.sum())
                rows = []
                for code, n in counts.items():
                    rows.append({
                        tr("Código original","Original code"): int(code) if float(code).is_integer() else code,
                        "N": int(n),
                        tr("Percentual (%)","Percentage (%)"): round(100*int(n)/total,2) if total else 0,
                        tr("Comparação Foken","Foken comparison"): classify(code),
                    })
                qtable = pd.DataFrame(rows)
                show_table(qtable)

                fig = go.Figure()
                for code in sorted(s.unique()):
                    mask = pd.to_numeric(sub[qc],errors="coerce") == code
                    fig.add_trace(go.Scattergl(
                        x=sub.loc[mask,"TIMESTAMP"],
                        y=np.full(mask.sum(),code),
                        mode="markers",
                        name=f"{tr('Código','Code')} {int(code) if float(code).is_integer() else code}",
                        marker=dict(color=qc_color(code),size=6),
                    ))
                fig.update_layout(
                    xaxis_title=tr("Data e hora","Date and time"),
                    yaxis_title=tr("Código QC original","Original QC code"),
                    height=430,
                )
                fig.update_xaxes(range=[start,end])
                st.plotly_chart(fig,use_container_width=True)

# ============================================================
# Sobre os Dados
# ============================================================

elif page_key == "about":
    st.header(tr("Sobre os Dados", "About the Data"))

    st.markdown(tr(
        """
### Camada 1 — Dados originais da torre
Arquivos Campbell Scientific **TOA5** do datalogger **CR3000**, preservando os cabeçalhos,
unidades e códigos de processamento (`Avg`, `Tot`, `Min`, `Max`, `WVc` etc.).

### Camada 2 — Eddy Covariance e QA/QC
Fluxos e indicadores de qualidade devem permanecer separados das observações meteorológicas
do datalogger, mesmo quando são pareados por timestamp.

### Camada 3 — Produtos processados
Séries preenchidas, NEE, GPP, Reco, incertezas e demais produtos derivados são apresentados
como produtos de processamento, não como observações instrumentais brutas.

### Continuidade temporal
O EcoFlux detecta lacunas reais pela diferença entre timestamps consecutivos e não desenha
uma linha contínua através dessas interrupções nas resoluções observacionais nativas.
""",
        """
### Layer 1 — Original tower data
Campbell Scientific **TOA5** files from the **CR3000** datalogger, preserving headers,
units and processing codes (`Avg`, `Tot`, `Min`, `Max`, `WVc`, etc.).

### Layer 2 — Eddy Covariance and QA/QC
Fluxes and quality indicators remain separate from datalogger meteorological observations,
even when paired by timestamp.

### Layer 3 — Processed products
Gap-filled series, NEE, GPP, Reco, uncertainties and other derived products are presented
as processing products rather than raw instrumental observations.

### Temporal continuity
EcoFlux detects real gaps from consecutive timestamps and does not draw continuous lines
through those interruptions at native observational resolutions.
"""
    ))

# ============================================================
# Solicitar Dados
# ============================================================

elif page_key == "request":
    st.header(tr("Solicitar Dados", "Request Data"))
    st.write(tr(
        "Os dados brutos não são disponibilizados para download público direto. "
        "Solicitações dependem de autorização explícita do responsável pelo conjunto de dados.",
        "Raw data are not made available for direct public download. "
        "Requests require explicit authorization from the data owner.",
    ))

    with st.form("request_form_v29"):
        nome = st.text_input(tr("Nome","Name"))
        email = st.text_input(tr("E-mail","Email"))
        inst = st.text_input(tr("Instituição","Institution"))
        purpose = st.text_area(tr("Finalidade científica / uso pretendido","Scientific purpose / intended use"))
        period = st.text_input(tr("Período de interesse","Period of interest"))
        vars_req = st.text_area(tr("Variáveis de interesse","Variables of interest"))
        submitted = st.form_submit_button(tr("Preparar solicitação","Prepare request"))

    if submitted:
        st.success(tr(
            "Solicitação preparada. Esta versão não envia nem armazena o formulário automaticamente.",
            "Request prepared. This version does not automatically send or store the form.",
        ))
