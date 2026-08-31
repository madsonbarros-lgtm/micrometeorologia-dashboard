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
    df = pd.read_excel(uploaded_file, sheet_name=sheet).copy()

    # Localiza a coluna temporal real.
    timestamp_candidates = [
        c for c in df.columns
        if str(c).strip().lower() in {"timestamp", "datetime", "date_time", "datatime"}
    ]
    if not timestamp_candidates:
        raise ValueError(
            "Não foi encontrada uma coluna temporal do tipo TIMESTAMP/DATETIME."
        )

    timestamp_col = timestamp_candidates[0]
    df["TIMESTAMP_parsed"] = pd.to_datetime(df[timestamp_col], errors="coerce")
    df = df[df["TIMESTAMP_parsed"].notna()].copy()
    df = df.sort_values("TIMESTAMP_parsed").reset_index(drop=True)

    # Converte apenas colunas que possuem conteúdo numérico útil.
    for c in df.columns:
        if str(c).strip().lower() not in NON_SCIENTIFIC_NAMES:
            converted = pd.to_numeric(df[c], errors="coerce")
            if converted.notna().sum() > 0:
                df[c] = converted

    return df, sheet, timestamp_col

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

def plot_variable(df, var, resolution, title=None):
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
        yaxis_title=var,
        hovermode="x unified",
        height=470,
        margin=dict(l=20, r=20, t=55, b=20),
    )
    st.plotly_chart(fig, use_container_width=True)

def stats_block(df, var):
    s = pd.to_numeric(df[var], errors="coerce")
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("N válido", f"{s.notna().sum():,}".replace(",", "."))
    c2.metric("Média", f"{s.mean():.3f}" if s.notna().any() else "—")
    c3.metric("Mediana", f"{s.median():.3f}" if s.notna().any() else "—")
    c4.metric("Desvio-padrão", f"{s.std():.3f}" if s.notna().any() else "—")
    c5.metric("Disponibilidade", f"{valid_pct(s):.1f}%")

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

def variable_analysis_panel(df, variable_options, key_prefix, full_start, full_end, heading=None):
    if not variable_options:
        st.info("Nenhuma variável científica correspondente foi encontrada.")
        return

    if heading:
        st.subheader(heading)

    var = st.selectbox(
        "Variável científica",
        variable_options,
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
        title=f"{var} | {start_dt:%d/%m/%Y %H:%M} a {end_dt:%d/%m/%Y %H:%M}",
    )
    stats_block(selected, var)

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
    df, sheet_name, timestamp_col = load_original_xlsx(uploaded)
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
