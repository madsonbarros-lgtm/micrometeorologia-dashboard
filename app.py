import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go

st.set_page_config(
    page_title="EcoFlux Brasil",
    page_icon="🌱",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
    .block-container {padding-top: 1.15rem; padding-bottom: 2rem; max-width: 1500px;}
    h1, h2, h3 {letter-spacing: -0.02em;}
    [data-testid="stMetricValue"] {font-size: 1.45rem;}
    </style>
    """,
    unsafe_allow_html=True,
)

# ------------------------------------------------------------
# Configuração
# ------------------------------------------------------------

# Colunas temporais, de índice ou administrativas:
# NÃO devem aparecer como "variáveis científicas" para análise.
NON_SCIENTIFIC_NAMES = {
    "timestamp", "timestamp_parsed", "datetime", "date_time", "datatime",
    "date", "time", "doy", "day_of_year", "julian_day", "julian",
    "year", "month", "day", "hour", "minute", "second",
    "daytime", "nighttime", "day_night", "daynight", "is_day", "is_night",
    "filename", "file", "record", "index", "unnamed: 0"
}

@st.cache_data(show_spinner=False)
def load_original_xlsx(uploaded_file):
    xls = pd.ExcelFile(uploaded_file)
    sheet = xls.sheet_names[0]
    raw = pd.read_excel(uploaded_file, sheet_name=sheet).copy()

    # Localiza a coluna temporal real.
    timestamp_candidates = [
        c for c in raw.columns
        if str(c).strip().lower() in {"timestamp", "datetime", "date_time", "datatime"}
    ]
    if not timestamp_candidates:
        raise ValueError(
            "Não foi encontrada uma coluna temporal do tipo TIMESTAMP/DATETIME."
        )

    timestamp_col = timestamp_candidates[0]

    # Extrai unidades da primeira linha não temporal, quando ela existir.
    # Na planilha original, a linha de unidades não possui TIMESTAMP válido.
    timestamp_probe = pd.to_datetime(raw[timestamp_col], errors="coerce")
    unit_rows = raw[timestamp_probe.isna()].copy()

    units = {}
    if not unit_rows.empty:
        candidate = unit_rows.iloc[0]
        for c in raw.columns:
            value = candidate.get(c)
            if pd.notna(value):
                text = str(value).strip()
                if text and text.lower() not in {"nan", "none", "-", "--"}:
                    units[c] = text

    df = raw.copy()
    df["TIMESTAMP_parsed"] = pd.to_datetime(df[timestamp_col], errors="coerce")
    df = df[df["TIMESTAMP_parsed"].notna()].copy()
    df = df.sort_values("TIMESTAMP_parsed").reset_index(drop=True)

    # Converte apenas colunas que possuem conteúdo numérico útil.
    for c in df.columns:
        if str(c).strip().lower() not in NON_SCIENTIFIC_NAMES:
            converted = pd.to_numeric(df[c], errors="coerce")
            if converted.notna().sum() > 0:
                df[c] = converted

    return df, sheet, timestamp_col, units


def is_qc_variable_name(name):
    """
    Identifica qualquer coluna de controle de qualidade.
    Exemplos: qc_LE, qc_co2_flux, FP_qc e nomes que contenham qc_/_qc.
    """
    n = str(name).strip().lower()
    return (
        n.startswith("qc_")
        or "qc_" in n
        or n.endswith("_qc")
        or "_qc" in n
    )

def associated_qc_variable(var, columns):
    """
    Procura a coluna QC associada à variável física.
    Prioridade: qc_<variável>, depois <variável>_qc.
    """
    cols = {str(c).strip().lower(): c for c in columns}
    name = str(var).strip()

    candidates = [
        f"qc_{name}".lower(),
        f"{name}_qc".lower(),
    ]
    for candidate in candidates:
        if candidate in cols:
            return cols[candidate]
    return None

def physical_scientific_columns(df):
    """
    Variáveis físicas/científicas comparáveis:
    numéricas, não temporais/administrativas e não QC.
    """
    cols = []
    for c in df.columns:
        if is_scientific_variable(df, c) and not is_qc_variable_name(c):
            cols.append(c)
    return cols

def qc_columns(df):
    """Colunas numéricas de controle de qualidade."""
    return [
        c for c in df.columns
        if is_qc_variable_name(c) and pd.api.types.is_numeric_dtype(df[c])
    ]

def is_scientific_variable(col, df):
    name = str(col).strip().lower()
    if name in NON_SCIENTIFIC_NAMES:
        return False

    # Também exclui variantes óbvias de tempo/data.
    time_tokens = [
        "timestamp", "datetime", "datatime", "day_of_year",
        "daytime", "nighttime", "day_night", "daynight",
        "is_day", "is_night"
    ]
    if any(token in name for token in time_tokens):
        return False

    return pd.api.types.is_numeric_dtype(df[col])

def scientific_columns(df):
    return [c for c in df.columns if is_scientific_variable(c, df)]

def existing_scientific(df, names):
    available = scientific_columns(df)
    return [c for c in names if c in available]

def valid_pct(s):
    return 100 * s.notna().mean() if len(s) else np.nan


def _unit_key_lookup(units):
    return {str(k).strip().lower(): k for k in units.keys()}

def base_variable_for_unit(var, units):
    """
    Resolve a variável-base de campos correlatos como qc_LE -> LE.
    A unidade herdada é preservada exatamente como aparece na planilha.
    """
    name = str(var).strip()
    lower = name.lower()
    lookup = _unit_key_lookup(units)

    prefixes = ["qc_", "rand_err_", "random_error_", "uncertainty_"]
    for prefix in prefixes:
        if lower.startswith(prefix):
            candidate = lower[len(prefix):]
            if candidate in lookup:
                return lookup[candidate]

    suffixes = ["_qc", "_sd", "_se", "_uncertainty", "_error"]
    for suffix in suffixes:
        if lower.endswith(suffix):
            candidate = lower[:-len(suffix)]
            if candidate in lookup:
                return lookup[candidate]

    return None

def unit_only(var, units):
    """
    QC representa classe/nível de qualidade e não possui unidade física.
    Demais variáveis mantêm exatamente a unidade registrada na planilha.
    """
    if is_qc_variable_name(var):
        return "sem unidade"

    direct = units.get(var)
    if direct is not None and str(direct).strip():
        return str(direct).strip()

    lookup = _unit_key_lookup(units)
    real_key = lookup.get(str(var).strip().lower())
    if real_key is not None:
        direct = units.get(real_key)
        if direct is not None and str(direct).strip():
            return str(direct).strip()

    return "unidade não informada"

def unit_label(var, units):
    unit = unit_only(var, units)
    if unit in {"unidade não informada", "sem unidade"}:
        return str(var)
    return f"{var} [{unit}]"

def variable_valid_range(df, var):
    if var not in df.columns:
        return None, None, 0

    s = pd.to_numeric(df[var], errors="coerce")
    mask = s.notna() & df["TIMESTAMP_parsed"].notna()

    if not mask.any():
        return None, None, 0

    times = df.loc[mask, "TIMESTAMP_parsed"]
    return times.min(), times.max(), int(mask.sum())

def show_variable_availability(df, variables, selected_start, selected_end, units):
    rows = []
    has_partial = False

    for var in variables:
        first_valid, last_valid, n_valid = variable_valid_range(df, var)

        if first_valid is None:
            coverage = "Sem dados válidos"
            status = "Sem dados"
            has_partial = True
        else:
            coverage = f"{first_valid:%d/%m/%Y %H:%M} → {last_valid:%d/%m/%Y %H:%M}"
            fully_covers = first_valid <= selected_start and last_valid >= selected_end
            status = "Cobre todo o período" if fully_covers else "Cobertura parcial"
            if not fully_covers:
                has_partial = True

        rows.append({
            "Variável": var,
            "Unidade": unit_only(var, units),
            "Dados válidos disponíveis": coverage,
            "N válido no arquivo": n_valid,
            "Situação no período selecionado": status,
        })

    st.markdown("#### Disponibilidade temporal das variáveis")
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

    if has_partial:
        st.info(
            "O período selecionado pode ser maior que a cobertura real de uma ou mais variáveis. "
            "O gráfico mantém o intervalo solicitado no eixo X, mas a linha aparece somente onde "
            "existem valores válidos."
        )

def add_missing_period_shading(fig, df_full, variables, selected_start, selected_end):
    """
    Sombreia trechos do período solicitado fora da cobertura temporal
    conjunta das variáveis selecionadas.
    """
    firsts, lasts = [], []

    for var in variables:
        first_valid, last_valid, _ = variable_valid_range(df_full, var)
        if first_valid is not None:
            firsts.append(first_valid)
            lasts.append(last_valid)

    if not firsts:
        return fig

    coverage_start = min(firsts)
    coverage_end = max(lasts)

    if selected_start < coverage_start:
        fig.add_vrect(
            x0=selected_start,
            x1=coverage_start,
            fillcolor="lightgray",
            opacity=0.18,
            line_width=0,
            annotation_text="Sem dados válidos",
            annotation_position="top left",
        )

    if coverage_end < selected_end:
        fig.add_vrect(
            x0=coverage_end,
            x1=selected_end,
            fillcolor="lightgray",
            opacity=0.18,
            line_width=0,
            annotation_text="Sem dados válidos",
            annotation_position="top left",
        )

    return fig

def filter_period(df, start_dt, end_dt):
    return df[
        (df["TIMESTAMP_parsed"] >= start_dt)
        & (df["TIMESTAMP_parsed"] <= end_dt)
    ].copy()

def aggregate_time(df, var, resolution):
    d = df[["TIMESTAMP_parsed", var]].copy().set_index("TIMESTAMP_parsed")

    if resolution == "30 min":
        return d.reset_index()

    rule = {
        "Horário": "1h",
        "Diário": "1D",
        "Semanal": "1W",
        "Mensal": "1MS",
    }[resolution]

    return d.resample(rule).mean(numeric_only=True).reset_index()


# Paleta de cores distintas e estáveis para as séries científicas.
# A mesma variável mantém a mesma cor em todas as páginas/gráficos.
VARIABLE_PALETTE = [
    "#1f77b4",  # azul
    "#d62728",  # vermelho
    "#2ca02c",  # verde
    "#9467bd",  # roxo
    "#ff7f0e",  # laranja
    "#17becf",  # ciano
    "#8c564b",  # marrom
    "#e377c2",  # rosa
    "#bcbd22",  # oliva
    "#7f7f7f",  # cinza
    "#393b79",
    "#637939",
    "#8c6d31",
    "#843c39",
    "#7b4173",
    "#3182bd",
    "#31a354",
    "#756bb1",
    "#e6550d",
    "#636363",
]

def variable_color(var):
    """
    Cor estável por nome de variável.
    Evita trocar a cor da mesma variável entre páginas e sessões.
    """
    text = str(var)
    idx = sum((i + 1) * ord(ch) for i, ch in enumerate(text)) % len(VARIABLE_PALETTE)
    return VARIABLE_PALETTE[idx]

def colors_for_variables(variables):
    """
    Garante cores distintas dentro de um mesmo gráfico.
    """
    used = set()
    mapping = {}

    for var in variables:
        preferred = variable_color(var)
        if preferred not in used:
            color = preferred
        else:
            color = next((c for c in VARIABLE_PALETTE if c not in used), preferred)

        mapping[var] = color
        used.add(color)

    return mapping

def plot_variable(df, var, resolution, title=None, units=None):
    d = aggregate_time(df, var, resolution)

    if d.empty or d[var].notna().sum() == 0:
        st.warning("Não há valores válidos dessa variável no período informado.")
        return

    fig = go.Figure(
        go.Scattergl(
            x=d["TIMESTAMP_parsed"],
            y=d[var],
            mode="lines",
            name=var,
            line=dict(color=variable_color(var), width=2),
            connectgaps=False,
        )
    )
    fig.update_layout(
        title=title or f"{var} — período selecionado",
        xaxis_title="Data e hora",
        yaxis_title=unit_label(var, units or {}),
        hovermode="x unified",
        height=470,
        margin=dict(l=20, r=20, t=55, b=20),
    )
    st.plotly_chart(fig, use_container_width=True)

def stats_block(df, var, units=None):
    s = pd.to_numeric(df[var], errors="coerce")
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("N válido", f"{s.notna().sum():,}".replace(",", "."))
    c2.metric("Média", f"{s.mean():.3f}" if s.notna().any() else "—")
    c3.metric("Mediana", f"{s.median():.3f}" if s.notna().any() else "—")
    c4.metric("Desvio-padrão", f"{s.std():.3f}" if s.notna().any() else "—")
    c5.metric("Disponibilidade", f"{valid_pct(s):.1f}%")
    st.caption(f"Unidade de {var}: **{unit_only(var, units or {})}**")

def period_controls(key_prefix, full_start, full_end):
    st.markdown("#### Período da análise")

    c1, c2 = st.columns(2)
    start_date = c1.date_input(
        "Data inicial",
        value=full_start.date(),
        min_value=full_start.date(),
        max_value=full_end.date(),
        key=f"{key_prefix}_start_date",
        format="DD/MM/YYYY",
    )
    end_date = c2.date_input(
        "Data final",
        value=full_end.date(),
        min_value=full_start.date(),
        max_value=full_end.date(),
        key=f"{key_prefix}_end_date",
        format="DD/MM/YYYY",
    )

    c3, c4 = st.columns(2)
    start_time = c3.time_input(
        "Hora inicial",
        value=full_start.time().replace(second=0, microsecond=0),
        key=f"{key_prefix}_start_time",
    )
    end_time = c4.time_input(
        "Hora final",
        value=full_end.time().replace(second=0, microsecond=0),
        key=f"{key_prefix}_end_time",
    )

    start_dt = pd.Timestamp.combine(start_date, start_time)
    end_dt = pd.Timestamp.combine(end_date, end_time)

    return start_dt, end_dt



# Interpretação dos códigos QC usada no painel.
# Convenção usual dos flags de qualidade de fluxos por Eddy Covariance.
QC_MEANINGS = {
    0: "Alta qualidade — melhor classe de qualidade",
    1: "Qualidade intermediária — requer maior cautela na interpretação",
    2: "Baixa qualidade — pior classe de qualidade",
}


QC_CLASS_COLORS = {
    0: "#2ca02c",  # verde
    1: "#ff7f0e",  # laranja
    2: "#d62728",  # vermelho
}

def qc_color(value):
    try:
        numeric = float(value)
        if numeric.is_integer():
            numeric = int(numeric)
        return QC_CLASS_COLORS.get(numeric, "#7f7f7f")
    except Exception:
        return "#7f7f7f"

def qc_display_label(value):
    try:
        numeric = float(value)
        if numeric.is_integer():
            numeric = int(numeric)
        if numeric in QC_MEANINGS:
            short = {
                0: "Alta qualidade",
                1: "Qualidade intermediária",
                2: "Baixa qualidade",
            }[numeric]
            return f"{numeric} — {short}"
        return str(value)
    except Exception:
        return str(value)

def aggregate_qc_mode(df_period, qc_vars, resolution):
    """
    Para QC, agregação temporal usa a moda (classe mais frequente),
    nunca a média.
    """
    if resolution == "30 min":
        return df_period[["TIMESTAMP_parsed"] + qc_vars].copy()

    rule = {
        "Horário": "1h",
        "Diário": "1D",
        "Semanal": "1W",
        "Mensal": "1MS",
    }[resolution]

    def _mode_or_nan(s):
        s = pd.to_numeric(s, errors="coerce").dropna()
        if s.empty:
            return np.nan
        m = s.mode()
        return m.iloc[0] if not m.empty else np.nan

    out = (
        df_period[["TIMESTAMP_parsed"] + qc_vars]
        .set_index("TIMESTAMP_parsed")
        .resample(rule)
        .agg(_mode_or_nan)
        .reset_index()
    )
    return out

def qc_proportion_table(df_period, qc_var, resolution):
    """
    Proporção temporal das classes 0/1/2 em cada janela.
    """
    d = df_period[["TIMESTAMP_parsed", qc_var]].copy()
    d[qc_var] = pd.to_numeric(d[qc_var], errors="coerce")

    if resolution == "30 min":
        d["Periodo"] = d["TIMESTAMP_parsed"]
    else:
        rule = {
            "Horário": "1h",
            "Diário": "1D",
            "Semanal": "1W",
            "Mensal": "1MS",
        }[resolution]
        d = d.set_index("TIMESTAMP_parsed")
        rows = []
        for ts, group in d.groupby(pd.Grouper(freq=rule)):
            if pd.isna(ts):
                continue
            s = group[qc_var].dropna()
            if s.empty:
                continue
            counts = s.value_counts()
            total = counts.sum()
            row = {"Periodo": ts}
            for cls in [0, 1, 2]:
                row[cls] = 100 * counts.get(cls, 0) / total
            rows.append(row)
        return pd.DataFrame(rows)

    rows = []
    for _, r in d.dropna(subset=[qc_var]).iterrows():
        row = {"Periodo": r["Periodo"], 0: 0.0, 1: 0.0, 2: 0.0}
        val = r[qc_var]
        if val in [0, 1, 2]:
            row[int(val)] = 100.0
        rows.append(row)
    return pd.DataFrame(rows)

def qc_meaning(value):
    try:
        numeric = float(value)
        if numeric.is_integer():
            numeric = int(numeric)
        return QC_MEANINGS.get(
            numeric,
            f"Código {value} — significado não cadastrado"
        )
    except Exception:
        return f"Código {value} — significado não cadastrado"

def qc_quality_panel(df_period, var, all_columns, resolution):
    """
    Mostra a série QC associada à variável selecionada, sem tratá-la como grandeza física.
    Não interpreta o significado dos códigos QC; apenas apresenta os valores existentes.
    """
    qc_var = associated_qc_variable(var, all_columns)
    if qc_var is None:
        return

    st.markdown("#### Controle de qualidade associado")
    st.caption(
        f"`{qc_var}` é um indicador de qualidade associado a `{var}`. "
        "Os códigos são apresentados como registrados no arquivo e não possuem unidade física."
    )

    show_qc = st.checkbox(
        f"Mostrar {qc_var}",
        value=False,
        key=f"show_qc_{var}_{resolution}",
    )
    if not show_qc:
        return

    q = df_period[["TIMESTAMP_parsed", qc_var]].copy()
    q[qc_var] = pd.to_numeric(q[qc_var], errors="coerce")
    q = q.dropna(subset=[qc_var])

    if q.empty:
        st.info(f"Não há valores de {qc_var} no período selecionado.")
        return

    # QC é categórico/ordinal; não aplicar média em agregações.
    if resolution != "30 min":
        rule = {
            "Horário": "1h",
            "Diário": "1D",
            "Semanal": "1W",
            "Mensal": "1MS",
        }[resolution]

        # Usa a moda em cada janela; em empate, pandas retorna a primeira moda.
        def _mode_or_nan(s):
            m = s.mode(dropna=True)
            return m.iloc[0] if not m.empty else np.nan

        q = (
            q.set_index("TIMESTAMP_parsed")
             .resample(rule)[qc_var]
             .apply(_mode_or_nan)
             .reset_index()
             .dropna(subset=[qc_var])
        )

    fig = go.Figure()
    fig.add_trace(
        go.Scattergl(
            x=q["TIMESTAMP_parsed"],
            y=q[qc_var],
            mode="markers+lines",
            name=qc_var,
            line=dict(color="#111111", width=1.5),
            marker=dict(color="#111111", size=6, symbol="diamond"),
            connectgaps=False,
        )
    )
    fig.update_layout(
        title=f"Controle de qualidade — {qc_var}",
        xaxis_title="Data e hora",
        yaxis_title="Código de qualidade (sem unidade)",
        hovermode="x unified",
        height=320,
        margin=dict(l=20, r=20, t=50, b=20),
    )
    st.plotly_chart(fig, use_container_width=True)

    counts = (
        pd.to_numeric(df_period[qc_var], errors="coerce")
        .dropna()
        .value_counts()
        .sort_index()
        .rename_axis("Código QC")
        .reset_index(name="Número de registros")
    )
    st.dataframe(counts, use_container_width=True, hide_index=True)

def variable_analysis_panel(df, variable_options, key_prefix, full_start, full_end, units, heading=None):
    if not variable_options:
        st.info("Nenhuma variável científica correspondente foi encontrada.")
        return

    if heading:
        st.subheader(heading)

    var = st.selectbox(
        "Variável científica",
        variable_options,
        format_func=lambda x: unit_label(x, units),
        key=f"{key_prefix}_variable",
    )

    st.caption(
        "Escolha primeiro a variável e depois informe exatamente o período que deseja analisar."
    )

    start_dt, end_dt = period_controls(key_prefix, full_start, full_end)

    resolution = st.selectbox(
        "Resolução para visualização",
        ["30 min", "Horário", "Diário", "Semanal", "Mensal"],
        index=2,
        key=f"{key_prefix}_resolution",
    )

    if start_dt > end_dt:
        st.error("A data/hora inicial deve ser anterior à data/hora final.")
        return

    selected = filter_period(df, start_dt, end_dt)

    st.markdown(
        f"**Período selecionado:** {start_dt:%d/%m/%Y %H:%M} → "
        f"{end_dt:%d/%m/%Y %H:%M}"
    )

    if selected.empty:
        st.warning("Não há registros nesse período.")
        return

    st.caption(
        f"{len(selected):,} registros temporais encontrados no intervalo.".replace(",", ".")
    )

    plot_variable(
        selected,
        var,
        resolution,
        title=f"{unit_label(var, units)} | {start_dt:%d/%m/%Y %H:%M} a {end_dt:%d/%m/%Y %H:%M}",
        units=units,
    )
    stats_block(selected, var, units=units)


def aggregate_multiple(df, variables, resolution):
    d = df[["TIMESTAMP_parsed"] + variables].copy().set_index("TIMESTAMP_parsed")

    if resolution == "30 min":
        return d.reset_index()

    rule = {
        "Horário": "1h",
        "Diário": "1D",
        "Semanal": "1W",
        "Mensal": "1MS",
    }[resolution]

    return d.resample(rule).mean(numeric_only=True).reset_index()

def normalize_zscore(series):
    s = pd.to_numeric(series, errors="coerce")
    sd = s.std()
    if pd.isna(sd) or sd == 0:
        return s * np.nan
    return (s - s.mean()) / sd

def comparison_same_axis(data, variables, title, units):
    var_units = [unit_only(v, units) for v in variables]
    informed = [u for u in var_units if u != "unidade não informada"]
    same_unit = bool(informed) and len(set(informed)) == 1 and len(informed) == len(variables)

    # Se houver duas variáveis na mesma unidade, mas em escalas muito diferentes
    # (caso típico de uma variável e seu qc_), mantém os valores originais e usa
    # um segundo eixo Y para não "achatar" a série de menor magnitude.
    use_secondary = False
    if len(variables) == 2 and same_unit:
        ranges = []
        for v in variables:
            s = pd.to_numeric(data[v], errors="coerce").dropna()
            if s.empty:
                ranges.append(np.nan)
            else:
                r = float(s.max() - s.min())
                if r == 0:
                    r = float(s.abs().max())
                ranges.append(r)

        finite = [r for r in ranges if pd.notna(r) and r > 0]
        if len(finite) == 2:
            ratio = max(finite) / min(finite)
            use_secondary = ratio >= 10

    fig = go.Figure()
    color_map = colors_for_variables(variables)
    for i, var in enumerate(variables):
        trace_kwargs = dict(
            x=data["TIMESTAMP_parsed"],
            y=data[var],
            mode="lines",
            name=unit_label(var, units),
            line=dict(color=color_map[var], width=2),
            connectgaps=False,
        )
        if use_secondary and i == 1:
            trace_kwargs["yaxis"] = "y2"
        fig.add_trace(go.Scattergl(**trace_kwargs))

    common_unit = informed[0] if same_unit else None
    y_title = common_unit if common_unit else "Valor"

    layout_kwargs = dict(
        title=title,
        xaxis_title="Data e hora",
        yaxis=dict(title=y_title),
        hovermode="x unified",
        height=500,
        margin=dict(l=20, r=70 if use_secondary else 20, t=55, b=20),
    )

    if use_secondary:
        layout_kwargs["yaxis2"] = dict(
            title=common_unit,
            overlaying="y",
            side="right",
        )

    fig.update_layout(**layout_kwargs)
    st.plotly_chart(fig, use_container_width=True)

    if use_secondary:
        st.caption(
            "As duas séries estão em valores originais e na mesma unidade, mas usam eixos Y "
            "independentes porque suas magnitudes são muito diferentes. Isso evita que a série "
            "de menor amplitude pareça zerada."
        )

def comparison_two_axes(data, variables, title, units, df_full=None, selected_start=None, selected_end=None):
    if len(variables) != 2:
        st.warning("O modo de dois eixos Y requer exatamente duas variáveis.")
        return

    v1, v2 = variables
    color_map = colors_for_variables(variables)
    fig = go.Figure()

    fig.add_trace(
        go.Scattergl(
            x=data["TIMESTAMP_parsed"],
            y=data[v1],
            mode="lines",
            name=unit_label(v1, units),
            line=dict(color=color_map[v1], width=2),
            yaxis="y",
            connectgaps=False,
        )
    )
    fig.add_trace(
        go.Scattergl(
            x=data["TIMESTAMP_parsed"],
            y=data[v2],
            mode="lines",
            name=unit_label(v2, units),
            line=dict(color=color_map[v2], width=2),
            yaxis="y2",
            connectgaps=False,
        )
    )

    fig.update_layout(
        title=title,
        xaxis_title="Data e hora",
        yaxis=dict(
            title=unit_label(v1, units),
            titlefont=dict(color=color_map[v1]),
            tickfont=dict(color=color_map[v1]),
        ),
        yaxis2=dict(
            title=unit_label(v2, units),
            titlefont=dict(color=color_map[v2]),
            tickfont=dict(color=color_map[v2]),
            overlaying="y",
            side="right",
        ),
        hovermode="x unified",
        height=500,
        margin=dict(l=20, r=70, t=55, b=20),
    )

    if selected_start is not None and selected_end is not None:
        fig.update_xaxes(range=[selected_start, selected_end])

    if df_full is not None and selected_start is not None and selected_end is not None:
        add_missing_period_shading(
            fig,
            df_full,
            variables,
            selected_start,
            selected_end,
        )

    st.plotly_chart(fig, use_container_width=True)

def comparison_normalized(data, variables, title, units):
    nd = data[["TIMESTAMP_parsed"] + variables].copy()

    fig = go.Figure()
    color_map = colors_for_variables(variables)
    for var in variables:
        nd[var] = normalize_zscore(nd[var])
        fig.add_trace(
            go.Scattergl(
                x=nd["TIMESTAMP_parsed"],
                y=nd[var],
                mode="lines",
                name=unit_label(var, units),
                line=dict(color=color_map[var], width=2),
                connectgaps=False,
            )
        )

    fig.update_layout(
        title=title,
        xaxis_title="Data e hora",
        yaxis_title="Valor padronizado (z-score)",
        hovermode="x unified",
        height=500,
        margin=dict(l=20, r=20, t=55, b=20),
    )
    st.plotly_chart(fig, use_container_width=True)

def comparison_separate(data, variables, units):
    color_map = colors_for_variables(variables)
    for var in variables:
        fig = go.Figure(
            go.Scattergl(
                x=data["TIMESTAMP_parsed"],
                y=data[var],
                mode="lines",
                name=unit_label(var, units),
                line=dict(color=color_map[var], width=2),
                connectgaps=False,
            )
        )
        fig.update_layout(
            title=unit_label(var, units),
            xaxis_title="Data e hora",
            yaxis_title=unit_label(var, units),
            hovermode="x unified",
            height=330,
            margin=dict(l=20, r=20, t=50, b=20),
        )
        st.plotly_chart(fig, use_container_width=True)

# ------------------------------------------------------------
# Interface
# ------------------------------------------------------------

st.title("🌱 EcoFlux Brasil")
st.caption("Plataforma de Dados Micrometeorológicos e Fluxos Ecossistêmicos")

st.sidebar.header("Navegação")
page = st.sidebar.radio(
    "Seção",
    [
        "Visão Geral",
        "Explorador de Variáveis",
        "Comparar Variáveis",
        "Eddy Covariance",
        "Meteorologia",
        "Balanço de Energia",
        "Água e Evapotranspiração",
        "Qualidade dos Dados",
        "Sobre os Dados",
        "Solicitar Dados",
    ],
)

st.sidebar.divider()
uploaded = st.sidebar.file_uploader(
    "Carregar dados originais (XLSX)",
    type=["xlsx"],
    help="Uso durante o desenvolvimento. O arquivo bruto não é oferecido para download.",
)

st.sidebar.caption(
    "Visualização pública; dados brutos somente mediante autorização."
)

if uploaded is None:
    st.info("Carregue a planilha original para iniciar.")
    st.stop()

try:
    df, sheet_name, timestamp_col, units = load_original_xlsx(uploaded)
except Exception as e:
    st.error(f"Não foi possível ler a planilha: {e}")
    st.stop()

full_start = df["TIMESTAMP_parsed"].min()
full_end = df["TIMESTAMP_parsed"].max()
sci_vars = scientific_columns(df)
qc_vars = qc_columns(df)
sci_vars = [c for c in sci_vars if not is_qc_variable_name(c)]

# ------------------------------------------------------------
# VISÃO GERAL
# ------------------------------------------------------------

if page == "Visão Geral":
    st.header("Visão Geral")

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Registros", f"{len(df):,}".replace(",", "."))
    c2.metric("Variáveis científicas", len(sci_vars))
    c3.metric("Resolução original", "30 min")
    c4.metric("Cobertura", f"{(full_end - full_start).days} dias")

    st.markdown(
        f"**Período disponível:** {full_start:%d/%m/%Y %H:%M} → "
        f"{full_end:%d/%m/%Y %H:%M}"
    )

    st.info(
        f"`{timestamp_col}` é usado exclusivamente como referência temporal. "
        "Colunas como TIMESTAMP, DATETIME, DATATIME, DATE, TIME, DOY, DAYTIME "
        "e outros indicadores temporais não são tratadas como variáveis científicas."
    )

    key_vars = existing_scientific(
        df,
        [
            "co2_flux", "H", "LE", "h2o_flux", "u*", "TKE",
            "air_temperature", "RH", "VPD", "wind_speed",
            "met_Rg_i_Avg", "met_NET_Avg",
        ],
    )

    if key_vars:
        st.subheader("Disponibilidade de variáveis-chave")
        for start in range(0, len(key_vars[:10]), 5):
            cols = st.columns(min(5, len(key_vars[:10]) - start))
            for i, var in enumerate(key_vars[start:start+5]):
                cols[i].metric(var, f"{valid_pct(df[var]):.1f}%")

    st.subheader("Variáveis científicas disponíveis")
    availability = pd.DataFrame({
        "Variável": sci_vars,
        "Unidade": [unit_only(c, units) for c in sci_vars],
        "Disponibilidade (%)": [round(valid_pct(df[c]), 2) for c in sci_vars],
        "N válido": [int(df[c].notna().sum()) for c in sci_vars],
        "Ausentes": [int(df[c].isna().sum()) for c in sci_vars],
    })

    search = st.text_input(
        "Pesquisar variável científica",
        placeholder="Ex.: co2_flux, LE, VPD, air_temperature",
    )
    if search:
        availability = availability[
            availability["Variável"].str.contains(search, case=False, na=False)
        ]

    st.dataframe(availability, use_container_width=True, height=480)

# ------------------------------------------------------------
# EXPLORADOR DE VARIÁVEIS
# ------------------------------------------------------------

elif page == "Explorador de Variáveis":
    st.header("Explorador de Variáveis")

    st.write(
        "Aqui o usuário escolhe uma variável científica, informa o período desejado "
        "e o gráfico é gerado somente para esse intervalo."
    )

    search = st.text_input(
        "Pesquisar variável",
        placeholder="Digite parte do nome da variável",
        key="explorer_search",
    )

    options = sci_vars
    if search:
        options = [c for c in sci_vars if search.lower() in c.lower()]

    variable_analysis_panel(
        df,
        options,
        "explorer",
        full_start,
        full_end,
        units,
    )

# ------------------------------------------------------------
# COMPARAR VARIÁVEIS
# ------------------------------------------------------------

elif page == "Comparar Variáveis":
    st.header("Comparar Variáveis")

    st.write(
        "Selecione duas ou mais variáveis físicas/científicas e informe o período comum da comparação. "
        "Campos temporais e colunas qc_ não aparecem nesta lista. As qc_ são indicadores de qualidade e são tratadas separadamente."
    )

    st.caption(
        "Cada variável recebe uma cor distinta e mantém essa identidade visual nos gráficos do EcoFlux. "
        "Indicadores QC são exibidos separadamente em preto com marcadores em losango."
    )

    search = st.text_input(
        "Pesquisar variáveis",
        placeholder="Ex.: co2_flux, VPD, LE, air_temperature",
        key="compare_search",
    )

    compare_options = sci_vars
    if search:
        compare_options = [
            c for c in sci_vars if search.lower() in str(c).lower()
        ]

    selected_vars = st.multiselect(
        "Variáveis físicas/científicas para comparação",
        compare_options,
        format_func=lambda x: unit_label(x, units),
        key="compare_variables",
        help="Selecione pelo menos duas variáveis.",
    )

    start_dt, end_dt = period_controls("compare", full_start, full_end)

    resolution = st.selectbox(
        "Resolução para comparação",
        ["30 min", "Horário", "Diário", "Semanal", "Mensal"],
        index=2,
        key="compare_resolution",
    )

    mode = st.radio(
        "Forma de comparação",
        [
            "Gráficos separados",
            "Mesmo gráfico — valores originais",
            "Dois eixos Y",
            "Mesmo gráfico — normalizado (z-score)",
        ],
        key="compare_mode",
        help=(
            "Use valores originais apenas quando as escalas/unidades forem comparáveis. "
            "Para variáveis de grandezas diferentes, prefira gráficos separados, dois eixos Y "
            "ou normalização por z-score."
        ),
    )

    if start_dt > end_dt:
        st.error("A data/hora inicial deve ser anterior à data/hora final.")
    elif len(selected_vars) < 2:
        st.info("Selecione pelo menos duas variáveis científicas para iniciar a comparação.")
    else:
        selected = filter_period(df, start_dt, end_dt)

        st.markdown(
            f"**Período da comparação:** {start_dt:%d/%m/%Y %H:%M} → "
            f"{end_dt:%d/%m/%Y %H:%M}"
        )

        show_variable_availability(
            df,
            selected_vars,
            start_dt,
            end_dt,
            units,
        )

        if selected.empty:
            st.warning("Não há registros nesse período.")
        else:
            data = aggregate_multiple(selected, selected_vars, resolution)

            st.caption(
                f"{len(selected):,} registros temporais no intervalo; "
                f"{len(data):,} pontos após a agregação selecionada.".replace(",", ".")
            )

            if mode == "Gráficos separados":
                comparison_separate(data, selected_vars, units)

            elif mode == "Mesmo gráfico — valores originais":
                selected_units = [unit_only(v, units) for v in selected_vars]
                if len(set(selected_units)) > 1:
                    st.warning(
                        "As variáveis selecionadas têm unidades diferentes. O gráfico preserva "
                        "os valores originais; para comparação de padrão, considere o modo normalizado."
                    )
                comparison_same_axis(
                    data,
                    selected_vars,
                    "Comparação — valores originais",
                    units,
                )

            elif mode == "Dois eixos Y":
                comparison_two_axes(
                    data,
                    selected_vars,
                    "Comparação com dois eixos Y",
                    units,
                    df,
                    start_dt,
                    end_dt,
                )

            elif mode == "Mesmo gráfico — normalizado (z-score)":
                st.info(
                    "O z-score remove a unidade e coloca as séries em uma escala comparável. "
                    "Ele é útil para comparar padrões temporais, não magnitudes físicas."
                )
                comparison_normalized(
                    data,
                    selected_vars,
                    "Comparação normalizada (z-score)",
                    units,
                )

            st.subheader("Estatísticas do período")
            stats_rows = []
            for var in selected_vars:
                s = pd.to_numeric(selected[var], errors="coerce")
                stats_rows.append({
                    "Variável": var,
                    "Unidade": unit_only(var, units),
                    "N válido": int(s.notna().sum()),
                    "Disponibilidade (%)": round(valid_pct(s), 2),
                    "Média": s.mean(),
                    "Mediana": s.median(),
                    "Desvio-padrão": s.std(),
                    "Mínimo": s.min(),
                    "Máximo": s.max(),
                })
            st.dataframe(pd.DataFrame(stats_rows), use_container_width=True)

            st.subheader("Correlação no período")
            corr_data = data[selected_vars].copy()
            corr = corr_data.corr(method="pearson", min_periods=3)

            if corr.shape[0] >= 2:
                fig = px.imshow(
                    corr,
                    text_auto=".2f",
                    aspect="auto",
                    zmin=-1,
                    zmax=1,
                    title="Matriz de correlação de Pearson",
                )
                st.plotly_chart(fig, use_container_width=True)
                st.caption(
                    "A correlação é calculada apenas para o período e a resolução selecionados. "
                    "Correlação não implica causalidade."
                )

# ------------------------------------------------------------
# EDDY COVARIANCE
# ------------------------------------------------------------

elif page == "Eddy Covariance":
    st.header("Eddy Covariance")

    ec_vars = existing_scientific(
        df,
        [
            "co2_flux", "H", "LE", "h2o_flux",
            "Tau", "u*", "TKE", "ET"
        ],
    )

    variable_analysis_panel(
        df,
        ec_vars,
        "eddy",
        full_start,
        full_end,
        units,
    )

# ------------------------------------------------------------
# METEOROLOGIA
# ------------------------------------------------------------

elif page == "Meteorologia":
    st.header("Meteorologia")

    met_vars = existing_scientific(
        df,
        [
            "air_temperature", "RH", "VPD", "wind_speed", "wind_dir",
            "met_T_ar_Avg", "met_UR_ar", "met_Rg_i_Avg",
            "met_Rg_r_Avg", "met_G_Avg", "met_NET_Avg",
            "met_PPT_Tot", "met_WS_S_WVT", "met_WindDir_D1_WVT",
        ],
    )

    variable_analysis_panel(
        df,
        met_vars,
        "meteorology",
        full_start,
        full_end,
        units,
    )

# ------------------------------------------------------------
# BALANÇO DE ENERGIA
# ------------------------------------------------------------

elif page == "Balanço de Energia":
    st.header("Balanço de Energia")

    energy_vars = existing_scientific(
        df,
        ["H", "LE", "met_G_Avg", "met_NET_Avg"],
    )

    variable_analysis_panel(
        df,
        energy_vars,
        "energy",
        full_start,
        full_end,
        units,
    )

# ------------------------------------------------------------
# ÁGUA E ET
# ------------------------------------------------------------

elif page == "Água e Evapotranspiração":
    st.header("Água e Evapotranspiração")

    water_vars = existing_scientific(
        df,
        ["ET", "h2o_flux", "VPD", "met_PPT_Tot"],
    )

    variable_analysis_panel(
        df,
        water_vars,
        "water",
        full_start,
        full_end,
        units,
    )

# ------------------------------------------------------------
# QUALIDADE
# ------------------------------------------------------------

elif page == "Qualidade dos Dados":
    st.header("Qualidade dos Dados")

    st.write(
        "Todas as colunas identificadas como `qc_`/`_qc` ficam concentradas nesta página. "
        "Elas são indicadores de controle de qualidade, não variáveis físicas, e não possuem unidade."
    )

    st.subheader("Referência dos códigos QC")
    qc_reference = pd.DataFrame([
        {"Código QC": 0, "Significado": "Alta qualidade", "Descrição": QC_MEANINGS[0]},
        {"Código QC": 1, "Significado": "Qualidade intermediária", "Descrição": QC_MEANINGS[1]},
        {"Código QC": 2, "Significado": "Baixa qualidade", "Descrição": QC_MEANINGS[2]},
    ])
    st.dataframe(qc_reference, use_container_width=True, hide_index=True)

    if not qc_vars:
        st.info("Nenhuma coluna QC foi identificada no arquivo.")
    else:
        selected_qc = st.multiselect(
            "Indicadores de qualidade",
            qc_vars,
            default=[qc_vars[0]] if qc_vars else [],
            key="quality_qc_multi_v21",
        )

        start_dt, end_dt = period_controls("quality_v21", full_start, full_end)

        resolution_qc = st.selectbox(
            "Resolução temporal do QC",
            ["30 min", "Horário", "Diário", "Semanal", "Mensal"],
            index=2,
            key="quality_resolution_v21",
            help=(
                "Em 30 min, cada registro QC é mostrado individualmente. "
                "Nas resoluções agregadas, o EcoFlux mostra a proporção (%) das classes 0, 1 e 2."
            ),
        )

        if start_dt > end_dt:
            st.error("A data/hora inicial deve ser anterior à data/hora final.")
        elif not selected_qc:
            st.info("Selecione pelo menos um indicador QC.")
        else:
            qperiod = filter_period(df, start_dt, end_dt)

            st.markdown(
                f"**Período selecionado:** {start_dt:%d/%m/%Y %H:%M} → "
                f"{end_dt:%d/%m/%Y %H:%M}"
            )

            # Disponibilidade temporal real
            availability_rows = []
            for qc in selected_qc:
                first_valid, last_valid, n_valid = variable_valid_range(df, qc)
                availability_rows.append({
                    "Indicador QC": qc,
                    "Unidade": "sem unidade",
                    "Primeiro registro disponível": (
                        first_valid.strftime("%d/%m/%Y %H:%M") if first_valid is not None else "—"
                    ),
                    "Último registro disponível": (
                        last_valid.strftime("%d/%m/%Y %H:%M") if last_valid is not None else "—"
                    ),
                    "N válido no arquivo": n_valid,
                })

            st.subheader("Disponibilidade temporal")
            st.dataframe(
                pd.DataFrame(availability_rows),
                use_container_width=True,
                hide_index=True,
            )

            # KPIs globais do período, somando todos os QCs selecionados
            qc_values_all = []
            for qc in selected_qc:
                s = pd.to_numeric(qperiod[qc], errors="coerce").dropna()
                qc_values_all.extend(s.tolist())

            qc_values_all = pd.Series(qc_values_all, dtype="float64")
            total_qc = len(qc_values_all)

            pct0 = 100 * (qc_values_all == 0).sum() / total_qc if total_qc else 0.0
            pct1 = 100 * (qc_values_all == 1).sum() / total_qc if total_qc else 0.0
            pct2 = 100 * (qc_values_all == 2).sum() / total_qc if total_qc else 0.0

            st.subheader("Qualidade no período selecionado")
            c0, c1, c2, c3 = st.columns(4)
            c0.metric("QC 0 — Alta qualidade", f"{pct0:.1f}%")
            c1.metric("QC 1 — Intermediária", f"{pct1:.1f}%")
            c2.metric("QC 2 — Baixa qualidade", f"{pct2:.1f}%")
            c3.metric("Registros QC avaliados", f"{total_qc:,}".replace(",", "."))

            # Resumo por indicador
            summary_rows = []
            for qc in selected_qc:
                s = pd.to_numeric(qperiod[qc], errors="coerce")
                valid = s.dropna()
                total = len(valid)

                summary_rows.append({
                    "Indicador QC": qc,
                    "N válido no período": total,
                    "Disponibilidade (%)": round(valid_pct(s), 2),
                    "QC 0 (%)": round(100 * (valid == 0).sum() / total, 2) if total else 0.0,
                    "QC 1 (%)": round(100 * (valid == 1).sum() / total, 2) if total else 0.0,
                    "QC 2 (%)": round(100 * (valid == 2).sum() / total, 2) if total else 0.0,
                })

            st.subheader("Resumo por indicador")
            st.dataframe(
                pd.DataFrame(summary_rows),
                use_container_width=True,
                hide_index=True,
            )

            if resolution_qc == "30 min":
                st.subheader("Gráfico temporal dos códigos QC — 30 min")
                fig = go.Figure()

                offsets = np.linspace(-0.10, 0.10, len(selected_qc)) if len(selected_qc) > 1 else [0]

                for offset, qc in zip(offsets, selected_qc):
                    s = pd.to_numeric(qperiod[qc], errors="coerce")

                    for cls in [0, 1, 2]:
                        mask = s == cls
                        if not mask.any():
                            continue

                        fig.add_trace(
                            go.Scattergl(
                                x=qperiod.loc[mask, "TIMESTAMP_parsed"],
                                y=np.full(mask.sum(), cls + offset),
                                mode="markers",
                                name=f"{qc} — {qc_display_label(cls)}",
                                marker=dict(
                                    color=QC_CLASS_COLORS[cls],
                                    size=6,
                                    symbol="circle",
                                ),
                                customdata=np.column_stack([
                                    np.full(mask.sum(), cls),
                                    np.full(mask.sum(), qc_meaning(cls), dtype=object),
                                ]),
                                hovertemplate=(
                                    f"<b>{qc}</b><br>"
                                    "Data: %{x}<br>"
                                    "Código QC: %{customdata[0]}<br>"
                                    "Significado: %{customdata[1]}"
                                    "<extra></extra>"
                                ),
                            )
                        )

                fig.update_layout(
                    xaxis=dict(
                        title="Data e hora",
                        range=[start_dt, end_dt],
                    ),
                    yaxis=dict(
                        title="Classe de qualidade",
                        tickmode="array",
                        tickvals=[0, 1, 2],
                        ticktext=[
                            "0 — Alta qualidade",
                            "1 — Intermediária",
                            "2 — Baixa qualidade",
                        ],
                        range=[-0.35, 2.35],
                    ),
                    hovermode="closest",
                    height=500,
                    margin=dict(l=20, r=20, t=30, b=20),
                    legend_title="Indicador / classe",
                )
                st.plotly_chart(fig, use_container_width=True)

            else:
                st.subheader(f"Proporção das classes QC — resolução {resolution_qc.lower()}")
                st.caption(
                    "Cada gráfico mostra a porcentagem de registros QC 0, 1 e 2 em cada janela temporal. "
                    "Nenhuma classe é escondida por média ou moda."
                )

                for qc in selected_qc:
                    prop = qc_proportion_table(qperiod, qc, resolution_qc)

                    if prop.empty:
                        st.info(f"Sem dados para {qc} no período.")
                        continue

                    fig = go.Figure()

                    for cls in [0, 1, 2]:
                        if cls not in prop.columns:
                            prop[cls] = 0.0

                        fig.add_trace(
                            go.Bar(
                                x=prop["Periodo"],
                                y=prop[cls],
                                name=qc_display_label(cls),
                                marker=dict(color=QC_CLASS_COLORS[cls]),
                                hovertemplate=(
                                    f"<b>{qc}</b><br>"
                                    "Período: %{x}<br>"
                                    f"{qc_display_label(cls)}: "
                                    "%{y:.1f}%<extra></extra>"
                                ),
                            )
                        )

                    fig.update_layout(
                        title=qc,
                        barmode="stack",
                        xaxis=dict(
                            title="Data e hora",
                            range=[start_dt, end_dt],
                        ),
                        yaxis=dict(
                            title="Proporção dos registros (%)",
                            range=[0, 100],
                        ),
                        hovermode="x unified",
                        height=420,
                        margin=dict(l=20, r=20, t=50, b=20),
                        legend_title="Classe QC",
                    )
                    st.plotly_chart(fig, use_container_width=True)

            # Tabela detalhada
            st.subheader("Distribuição dos códigos no período")
            detail_rows = []

            for qc in selected_qc:
                s = pd.to_numeric(qperiod[qc], errors="coerce").dropna()
                counts = s.value_counts().sort_index()
                total = int(counts.sum())

                for value, count in counts.items():
                    display_value = int(value) if float(value).is_integer() else value
                    detail_rows.append({
                        "Indicador QC": qc,
                        "Código QC": display_value,
                        "Significado": qc_display_label(value),
                        "Número de registros": int(count),
                        "Percentual (%)": round(
                            100 * int(count) / total, 2
                        ) if total else 0.0,
                    })

            if detail_rows:
                st.dataframe(
                    pd.DataFrame(detail_rows),
                    use_container_width=True,
                    hide_index=True,
                )

            with st.expander("Ver registros QC por data e hora"):
                qtable = qperiod[["TIMESTAMP_parsed"] + selected_qc].copy()
                qtable = qtable.rename(columns={"TIMESTAMP_parsed": "TIMESTAMP"})

                for qc in selected_qc:
                    qtable[f"Significado — {qc}"] = qtable[qc].apply(
                        lambda v: qc_display_label(v) if pd.notna(v) else "Sem dado"
                    )

                st.dataframe(
                    qtable,
                    use_container_width=True,
                    hide_index=True,
                )

elif page == "Sobre os Dados":
    st.header("Sobre os Dados")

    st.markdown(
        f"""
        ### Estrutura temporal
        O eixo temporal utiliza `{timestamp_col}` e serve apenas para localizar cada observação
        no tempo. Ele não é apresentado como variável científica.

        **Período total disponível:**  
        {full_start:%d/%m/%Y %H:%M} → {full_end:%d/%m/%Y %H:%M}

        ### Unidades de medida
        Quando a planilha original informa a unidade na linha de metadados, o EcoFlux a exibe
        exatamente como está registrada, sem corrigir, substituir ou reinterpretar caracteres.
        Todas as colunas `qc_`/`_qc` são indicadores de controle de qualidade sem unidade física e ficam concentradas exclusivamente na página Qualidade dos Dados.

        ### Variáveis científicas
        A lista de variáveis exclui automaticamente campos temporais e administrativos,
        incluindo `TIMESTAMP`, `DATETIME`, `DATATIME`, `DATE`, `TIME`, `DOY`, `DAYTIME`,
        `NIGHTTIME` e outros campos auxiliares de tempo/período.

        ### Forma de análise
        Em cada módulo o usuário escolhe uma variável científica e informa o período específico
        que deseja analisar. O gráfico e as estatísticas são então calculados somente para esse
        intervalo.

        ### Política de acesso
        A plataforma permite visualização científica, mas não oferece download público direto
        dos dados brutos. O fornecimento do conjunto depende de autorização.
        """
    )

# ------------------------------------------------------------
# SOLICITAR DADOS
# ------------------------------------------------------------

elif page == "Solicitar Dados":
    st.header("Solicitar Dados")

    st.warning(
        "Não há download público direto. O fornecimento de dados depende de autorização."
    )

    with st.form("request_form"):
        name = st.text_input("Nome")
        institution = st.text_input("Instituição")
        email = st.text_input("E-mail")
        variable = st.selectbox(
            "Variável científica de interesse",
            ["Selecione..."] + sci_vars,
        )
        requested_start = st.date_input(
            "Data inicial solicitada",
            value=full_start.date(),
            format="DD/MM/YYYY",
        )
        requested_end = st.date_input(
            "Data final solicitada",
            value=full_end.date(),
            format="DD/MM/YYYY",
        )
        purpose = st.text_area("Finalidade científica ou acadêmica")
        agreement = st.checkbox(
            "Declaro que o acesso depende de autorização prévia."
        )
        submitted = st.form_submit_button("Preparar solicitação")

        if submitted:
            if not name or not email or not purpose or not agreement:
                st.error(
                    "Preencha nome, e-mail e finalidade e confirme a declaração."
                )
            else:
                st.success(
                    "Solicitação preparada. Nesta versão, ela ainda não é enviada ou armazenada automaticamente."
                )

st.divider()
st.caption(
    "EcoFlux Brasil • Visualização científica pública • Dados brutos somente mediante autorização"
)
