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

def unit_label(var, units):
    unit = unit_only(var, units)
    if unit == "unidade não informada":
        return var
    return f"{var} [{unit}]"

def base_variable_for_unit(var, units):
    """
    Variáveis correlatas/flags recebem a mesma unidade da variável-base.
    A unidade é preservada EXATAMENTE como aparece na planilha.
    """
    name = str(var)

    prefixes = ["qc_", "rand_err_", "random_error_", "uncertainty_"]
    for prefix in prefixes:
        if name.startswith(prefix):
            candidate = name[len(prefix):]
            if candidate in units:
                return candidate

    suffixes = ["_qc", "_sd", "_se", "_uncertainty", "_error"]
    for suffix in suffixes:
        if name.endswith(suffix):
            candidate = name[:-len(suffix)]
            if candidate in units:
                return candidate

    return None

def unit_only(var, units):
    # Para variáveis correlatas (ex.: qc_LE, qc_co2_flux), a unidade da variável-base
    # tem prioridade, inclusive quando a planilha traz marcadores genéricos como [#].
    base = base_variable_for_unit(var, units)
    if base:
        inherited = units.get(base)
        if inherited is not None and str(inherited).strip():
            return str(inherited).strip()

    # Demais variáveis usam exatamente a unidade registrada na própria coluna.
    direct = units.get(var)
    if direct is not None and str(direct).strip():
        return str(direct).strip()

    return "unidade não informada"

def unit_label(var, units):
    unit = unit_only(var, units)
    if unit == "unidade não informada":
        return var
    return f"{var} [{unit}]"

def clean_unit_text(unit):
    """Normaliza problemas comuns de codificação e notação da linha de unidades."""
    if unit is None:
        return None

    text = str(unit).strip()
    if not text:
        return None

    # Corrige mojibake comum de UTF-8/Latin-1.
    replacements = {
        "Âµ": "µ",
        "Â°": "°",
        "Â": "",
        "+1": "",
        "+2": "²",
        "+3": "³",
    }
    for old, new in replacements.items():
        text = text.replace(old, new)

    # Melhora a notação dos expoentes negativos mais comuns.
    text = (
        text.replace("m-2", "m⁻²")
            .replace("m-1", "m⁻¹")
            .replace("s-1", "s⁻¹")
            .replace("kg-1", "kg⁻¹")
    )

    return text.strip()

def base_variable_for_unit(var, units):
    """
    Variáveis correlatas/flags recebem a mesma unidade física da variável-base
    quando a unidade própria estiver ausente ou inadequada.
    """
    name = str(var)

    # qc_LE -> LE ; qc_co2_flux -> co2_flux
    prefixes = ["qc_", "rand_err_", "random_error_", "uncertainty_"]
    for prefix in prefixes:
        if name.startswith(prefix):
            candidate = name[len(prefix):]
            if candidate in units:
                return candidate

    # LE_qc -> LE ; co2_flux_qc -> co2_flux
    suffixes = ["_qc", "_sd", "_se", "_uncertainty", "_error"]
    for suffix in suffixes:
        if name.endswith(suffix):
            candidate = name[:-len(suffix)]
            if candidate in units:
                return candidate

    return None

def unit_only(var, units):
    # 1) usa a unidade diretamente documentada
    direct = clean_unit_text(units.get(var))
    if direct:
        return direct

    # 2) para variável correlata, herda a unidade da variável-base
    base = base_variable_for_unit(var, units)
    if base:
        inherited = clean_unit_text(units.get(base))
        if inherited:
            return inherited

    return "unidade não informada"

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
    for i, var in enumerate(variables):
        trace_kwargs = dict(
            x=data["TIMESTAMP_parsed"],
            y=data[var],
            mode="lines",
            name=unit_label(var, units),
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

def comparison_two_axes(data, variables, title, units):
    if len(variables) != 2:
        st.warning("O modo de dois eixos Y requer exatamente duas variáveis.")
        return

    v1, v2 = variables
    fig = go.Figure()

    fig.add_trace(
        go.Scattergl(
            x=data["TIMESTAMP_parsed"],
            y=data[v1],
            mode="lines",
            name=unit_label(v1, units),
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
            yaxis="y2",
            connectgaps=False,
        )
    )

    fig.update_layout(
        title=title,
        xaxis_title="Data e hora",
        yaxis=dict(title=unit_label(v1, units)),
        yaxis2=dict(
            title=unit_label(v2, units),
            overlaying="y",
            side="right",
        ),
        hovermode="x unified",
        height=500,
        margin=dict(l=20, r=70, t=55, b=20),
    )
    st.plotly_chart(fig, use_container_width=True)

def comparison_normalized(data, variables, title, units):
    nd = data[["TIMESTAMP_parsed"] + variables].copy()

    fig = go.Figure()
    for var in variables:
        nd[var] = normalize_zscore(nd[var])
        fig.add_trace(
            go.Scattergl(
                x=nd["TIMESTAMP_parsed"],
                y=nd[var],
                mode="lines",
                name=unit_label(var, units),
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
    for var in variables:
        fig = go.Figure(
            go.Scattergl(
                x=data["TIMESTAMP_parsed"],
                y=data[var],
                mode="lines",
                name=unit_label(var, units),
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
        "Selecione duas ou mais variáveis científicas e informe o período comum da comparação. "
        "TIMESTAMP, DOY, DAYTIME e outros campos temporais não aparecem como variáveis científicas."
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
        "Variáveis científicas para comparação",
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

    qc_vars = [
        c for c in sci_vars
        if str(c).lower().startswith("qc_")
        or "quality" in str(c).lower()
        or "error" in str(c).lower()
    ]

    if not qc_vars:
        st.info("Nenhuma variável de qualidade foi identificada.")
    else:
        chosen = st.selectbox("Indicador de qualidade", qc_vars, key="qc_variable")
        start_dt, end_dt = period_controls("qc", full_start, full_end)

        if start_dt <= end_dt:
            selected = filter_period(df, start_dt, end_dt)

            st.markdown(
                f"**Período selecionado:** {start_dt:%d/%m/%Y %H:%M} → "
                f"{end_dt:%d/%m/%Y %H:%M}"
            )

            if selected.empty:
                st.warning("Não há registros nesse período.")
            else:
                s = selected[chosen].astype("string").fillna("NA")
                q = (
                    s.value_counts()
                    .rename_axis("Código")
                    .reset_index(name="Frequência")
                )
                q["Percentual (%)"] = (
                    100 * q["Frequência"] / q["Frequência"].sum()
                )

                fig = px.bar(
                    q,
                    x="Código",
                    y="Frequência",
                    text="Percentual (%)",
                    title=f"{chosen} — período selecionado",
                )
                fig.update_traces(texttemplate="%{text:.1f}%")
                st.plotly_chart(fig, use_container_width=True)
                st.dataframe(q, use_container_width=True)

# ------------------------------------------------------------
# SOBRE OS DADOS
# ------------------------------------------------------------

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
        Variáveis correlatas, como `qc_LE` e `qc_co2_flux`, usam prioritariamente a mesma
        unidade textual da variável-base correspondente, mesmo que a coluna correlata traga
        um marcador genérico como `[#]`. Assim, `LE [W+1m-2]` e `qc_LE [W+1m-2]`
        aparecem com a mesma unidade, assim como `co2_flux [Âµmol+1s-1m-2]` e
        `qc_co2_flux [Âµmol+1s-1m-2]`.

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
