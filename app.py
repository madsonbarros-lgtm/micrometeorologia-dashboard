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
    .small-note {font-size: 0.88rem; opacity: 0.8;}
    </style>
    """,
    unsafe_allow_html=True,
)

# ------------------------------------------------------------
# Leitura e preparação
# ------------------------------------------------------------

@st.cache_data(show_spinner=False)
def load_original_xlsx(uploaded_file):
    xls = pd.ExcelFile(uploaded_file)
    sheet = xls.sheet_names[0]
    df = pd.read_excel(uploaded_file, sheet_name=sheet).copy()

    if "TIMESTAMP" not in df.columns:
        raise ValueError("A coluna TIMESTAMP não foi encontrada.")

    df["TIMESTAMP_parsed"] = pd.to_datetime(df["TIMESTAMP"], errors="coerce")
    df = df[df["TIMESTAMP_parsed"].notna()].copy()
    df = df.sort_values("TIMESTAMP_parsed").reset_index(drop=True)

    # Converte para numérico apenas quando a conversão faz sentido.
    protected = {"TIMESTAMP", "TIMESTAMP_parsed", "filename", "date", "time"}
    for c in df.columns:
        if c not in protected:
            converted = pd.to_numeric(df[c], errors="coerce")
            # Só substitui se houver ao menos algum valor numérico útil.
            if converted.notna().sum() > 0:
                df[c] = converted

    return df, sheet

def existing(df, names):
    return [c for c in names if c in df.columns]

def numeric_columns(df):
    return [
        c for c in df.columns
        if c not in ["TIMESTAMP", "TIMESTAMP_parsed"]
        and pd.api.types.is_numeric_dtype(df[c])
    ]

def valid_pct(s):
    return 100 * s.notna().mean() if len(s) else np.nan

def aggregate_time(df, variables, resolution):
    variables = existing(df, variables)
    if not variables:
        return pd.DataFrame()

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

def line_chart(df, var, title, resolution, y_title=None):
    d = aggregate_time(df, [var], resolution)
    if d.empty:
        st.info("Sem dados para o período selecionado.")
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
        title=title,
        xaxis_title="Data e hora",
        yaxis_title=y_title or var,
        hovermode="x unified",
        height=430,
        margin=dict(l=20, r=20, t=55, b=20),
    )
    st.plotly_chart(fig, use_container_width=True)

def stats_cards(df, var):
    s = pd.to_numeric(df[var], errors="coerce")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Média", f"{s.mean():.3f}" if s.notna().any() else "—")
    c2.metric("Mediana", f"{s.median():.3f}" if s.notna().any() else "—")
    c3.metric("Desvio-padrão", f"{s.std():.3f}" if s.notna().any() else "—")
    c4.metric("Disponibilidade", f"{valid_pct(s):.1f}%")

def availability_table(df):
    cols = numeric_columns(df)
    return pd.DataFrame({
        "Variável": cols,
        "Disponibilidade (%)": [round(valid_pct(df[c]), 2) for c in cols],
        "Ausentes": [int(df[c].isna().sum()) for c in cols],
        "N válido": [int(df[c].notna().sum()) for c in cols],
    }).sort_values(["Disponibilidade (%)", "Variável"])

def quick_period_bounds(option, full_start, full_end):
    if option == "Série completa":
        return full_start, full_end
    days = {
        "Últimos 7 dias": 7,
        "Últimos 30 dias": 30,
        "Últimos 90 dias": 90,
        "Último ano": 365,
    }[option]
    start = max(full_start, full_end - pd.Timedelta(days=days))
    return start, full_end

# ------------------------------------------------------------
# Cabeçalho e navegação
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
st.sidebar.subheader("Fonte de dados")

uploaded = st.sidebar.file_uploader(
    "Carregar dados originais (XLSX)",
    type=["xlsx"],
    help="Uso para desenvolvimento. Na publicação final, o carregamento pode ser automatizado a partir de uma fonte privada.",
)

st.sidebar.caption(
    "Visualização pública; dados brutos somente mediante autorização."
)

if uploaded is None:
    st.info(
        "Carregue a planilha original para iniciar a análise. "
        "Depois podemos substituir este upload por carregamento automático protegido."
    )
    st.stop()

try:
    df, sheet_name = load_original_xlsx(uploaded)
except Exception as e:
    st.error(f"Não foi possível ler o arquivo: {e}")
    st.stop()

full_start = df["TIMESTAMP_parsed"].min()
full_end = df["TIMESTAMP_parsed"].max()

# ------------------------------------------------------------
# Filtro temporal global
# ------------------------------------------------------------

st.sidebar.divider()
st.sidebar.subheader("Período da análise")

period_mode = st.sidebar.radio(
    "Como escolher o período?",
    ["Atalhos", "Personalizado"],
)

if period_mode == "Atalhos":
    quick = st.sidebar.selectbox(
        "Período",
        ["Série completa", "Últimos 7 dias", "Últimos 30 dias", "Últimos 90 dias", "Último ano"],
        index=0,
    )
    start_dt, end_dt = quick_period_bounds(quick, full_start, full_end)

else:
    date_range = st.sidebar.date_input(
        "Datas",
        value=(full_start.date(), full_end.date()),
        min_value=full_start.date(),
        max_value=full_end.date(),
    )

    c1, c2 = st.sidebar.columns(2)
    start_time = c1.time_input("Hora inicial", value=full_start.time())
    end_time = c2.time_input("Hora final", value=full_end.time())

    if isinstance(date_range, tuple) and len(date_range) == 2:
        start_dt = pd.Timestamp.combine(date_range[0], start_time)
        end_dt = pd.Timestamp.combine(date_range[1], end_time)
    else:
        start_dt, end_dt = full_start, full_end

if start_dt > end_dt:
    st.sidebar.error("A data/hora inicial precisa ser anterior à final.")
    st.stop()

filtered = df[
    (df["TIMESTAMP_parsed"] >= start_dt)
    & (df["TIMESTAMP_parsed"] <= end_dt)
].copy()

st.sidebar.caption(
    f"Análise ativa: {start_dt:%d/%m/%Y %H:%M} → {end_dt:%d/%m/%Y %H:%M}"
)

resolution = st.sidebar.selectbox(
    "Agregação temporal",
    ["30 min", "Horário", "Diário", "Semanal", "Mensal"],
    index=2,
)

if filtered.empty:
    st.warning("Não há registros no período selecionado.")
    st.stop()

# Aviso global do período aplicado
st.success(
    f"Período analisado: **{start_dt:%d/%m/%Y %H:%M} → {end_dt:%d/%m/%Y %H:%M}** "
    f"• **{len(filtered):,} registros**".replace(",", ".")
)

# ------------------------------------------------------------
# VISÃO GERAL
# ------------------------------------------------------------

if page == "Visão Geral":
    st.header("Visão Geral")

    span_days = (end_dt - start_dt).total_seconds() / 86400
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Registros no período", f"{len(filtered):,}".replace(",", "."))
    c2.metric("Variáveis", len(numeric_columns(df)))
    c3.metric("Resolução original", "30 min")
    c4.metric("Período analisado", f"{span_days:.1f} dias")

    st.caption(f"Aba lida: {sheet_name}")

    # Cards de cobertura das variáveis-chave
    st.subheader("Cobertura das variáveis-chave")
    key_vars = existing(
        filtered,
        [
            "co2_flux", "H", "LE", "h2o_flux",
            "air_temperature", "RH", "VPD",
            "wind_speed", "met_Rg_i_Avg", "met_NET_Avg"
        ],
    )

    if key_vars:
        cols = st.columns(min(5, len(key_vars)))
        for i, var in enumerate(key_vars[:5]):
            cols[i].metric(var, f"{valid_pct(filtered[var]):.1f}%")

        if len(key_vars) > 5:
            cols2 = st.columns(min(5, len(key_vars) - 5))
            for i, var in enumerate(key_vars[5:10]):
                cols2[i].metric(var, f"{valid_pct(filtered[var]):.1f}%")

    avail = availability_table(filtered)

    st.subheader("Variáveis com maior ausência no período")
    top_missing = avail.sort_values("Disponibilidade (%)").head(10).copy()

    fig = px.bar(
        top_missing,
        x="Disponibilidade (%)",
        y="Variável",
        orientation="h",
        hover_data=["Ausentes", "N válido"],
        title="10 variáveis com menor disponibilidade",
    )
    fig.update_layout(
        height=480,
        yaxis={"categoryorder": "total descending"},
        margin=dict(l=10, r=10, t=55, b=10),
    )
    st.plotly_chart(fig, use_container_width=True)

    st.subheader("Tabela pesquisável de disponibilidade")
    search = st.text_input("Pesquisar variável", placeholder="Ex.: co2, VPD, qc, met_...")
    table_view = avail.copy()
    if search:
        table_view = table_view[
            table_view["Variável"].str.contains(search, case=False, na=False)
        ]
    st.dataframe(table_view, use_container_width=True, height=420)

# ------------------------------------------------------------
# EXPLORADOR
# ------------------------------------------------------------

elif page == "Explorador de Variáveis":
    st.header("Explorador de Variáveis")
    st.write(
        "Escolha qualquer variável numérica da planilha. "
        "O gráfico e as estatísticas abaixo usam exclusivamente o período selecionado na barra lateral."
    )

    vars_all = numeric_columns(filtered)
    search = st.text_input("Filtrar lista de variáveis", placeholder="Digite parte do nome")
    options = vars_all
    if search:
        options = [v for v in vars_all if search.lower() in v.lower()]

    if not options:
        st.warning("Nenhuma variável corresponde à busca.")
    else:
        var = st.selectbox("Variável", options)
        line_chart(filtered, var, f"{var} — período selecionado", resolution)
        stats_cards(filtered, var)

        st.subheader("Resumo estatístico")
        s = pd.to_numeric(filtered[var], errors="coerce")
        summary = pd.DataFrame({
            "Métrica": ["N válido", "Ausentes", "Média", "Mediana", "Desvio-padrão", "Mínimo", "Máximo"],
            "Valor": [
                int(s.notna().sum()),
                int(s.isna().sum()),
                s.mean(),
                s.median(),
                s.std(),
                s.min(),
                s.max(),
            ],
        })
        st.dataframe(summary, use_container_width=True)

# ------------------------------------------------------------
# EDDY COVARIANCE
# ------------------------------------------------------------

elif page == "Eddy Covariance":
    st.header("Eddy Covariance")

    sections = [
        ("Fluxo de CO₂", ["co2_flux"]),
        ("Fluxo de calor sensível", ["H"]),
        ("Fluxo de calor latente", ["LE"]),
        ("Fluxo de vapor d'água", ["h2o_flux"]),
        ("Velocidade de fricção", ["u*"]),
        ("Energia cinética turbulenta", ["TKE"]),
    ]

    for title, candidates in sections:
        opts = existing(filtered, candidates)
        if not opts:
            continue
        var = opts[0]
        st.subheader(title)
        line_chart(filtered, var, f"{title}: {var}", resolution)
        stats_cards(filtered, var)

# ------------------------------------------------------------
# METEOROLOGIA
# ------------------------------------------------------------

elif page == "Meteorologia":
    st.header("Meteorologia")

    sections = [
        ("Temperatura do ar", ["air_temperature", "met_T_ar_Avg"]),
        ("Umidade relativa", ["RH", "met_UR_ar"]),
        ("Déficit de pressão de vapor", ["VPD"]),
        ("Velocidade do vento", ["wind_speed", "met_WS_S_WVT"]),
        ("Direção do vento", ["wind_dir", "met_WindDir_D1_WVT"]),
        ("Radiação incidente", ["met_Rg_i_Avg"]),
        ("Radiação refletida", ["met_Rg_r_Avg"]),
    ]

    for title, opts in sections:
        vars_ok = existing(filtered, opts)
        if not vars_ok:
            continue
        var = st.selectbox(f"Variável — {title}", vars_ok, key=f"met_{title}")
        line_chart(filtered, var, f"{title}: {var}", resolution)
        stats_cards(filtered, var)

# ------------------------------------------------------------
# BALANÇO DE ENERGIA
# ------------------------------------------------------------

elif page == "Balanço de Energia":
    st.header("Balanço de Energia")

    energy_vars = existing(filtered, ["H", "LE", "met_G_Avg", "met_NET_Avg"])

    for var in energy_vars:
        line_chart(filtered, var, f"Componente: {var}", resolution)
        stats_cards(filtered, var)

    if all(v in filtered.columns for v in ["H", "LE", "met_G_Avg", "met_NET_Avg"]):
        st.subheader("Fechamento simplificado")
        d = filtered[["H", "LE", "met_G_Avg", "met_NET_Avg"]].dropna().copy()
        if not d.empty:
            d["Rn - G"] = d["met_NET_Avg"] - d["met_G_Avg"]
            d["H + LE"] = d["H"] + d["LE"]
            fig = px.scatter(
                d,
                x="Rn - G",
                y="H + LE",
                opacity=0.35,
                title="H + LE versus Rn - G — período selecionado",
            )
            st.plotly_chart(fig, use_container_width=True)
            st.caption(
                "Análise exploratória. A interpretação final depende da confirmação das unidades "
                "e das convenções de sinal."
            )

# ------------------------------------------------------------
# ÁGUA E ET
# ------------------------------------------------------------

elif page == "Água e Evapotranspiração":
    st.header("Água e Evapotranspiração")

    vars_ok = existing(filtered, ["ET", "h2o_flux", "VPD", "met_PPT_Tot"])
    if not vars_ok:
        st.info("Nenhuma das variáveis esperadas foi encontrada.")
    else:
        chosen = st.selectbox("Variável", vars_ok)
        line_chart(filtered, chosen, f"{chosen} — período selecionado", resolution)
        stats_cards(filtered, chosen)

# ------------------------------------------------------------
# QUALIDADE
# ------------------------------------------------------------

elif page == "Qualidade dos Dados":
    st.header("Qualidade dos Dados")

    qc_candidates = [
        c for c in filtered.columns
        if c.lower().startswith("qc_")
        or "quality" in c.lower()
        or "error" in c.lower()
    ]

    if qc_candidates:
        chosen = st.selectbox("Indicador de qualidade", qc_candidates)
        s = filtered[chosen].astype("string").fillna("NA")
        q = s.value_counts().rename_axis("Código").reset_index(name="Frequência")
        q["Percentual (%)"] = 100 * q["Frequência"] / q["Frequência"].sum()

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

    st.subheader("Disponibilidade por variável")
    avail = availability_table(filtered)

    search = st.text_input("Pesquisar variável nesta tabela", key="qc_search")
    if search:
        avail = avail[avail["Variável"].str.contains(search, case=False, na=False)]
    st.dataframe(avail, use_container_width=True, height=450)

# ------------------------------------------------------------
# SOBRE
# ------------------------------------------------------------

elif page == "Sobre os Dados":
    st.header("Sobre os Dados")

    st.markdown(
        f"""
        ### Série observacional
        Os dados são organizados a partir da coluna `TIMESTAMP`, com resolução original de **30 minutos**.

        **Período total disponível:** {full_start:%d/%m/%Y %H:%M} → {full_end:%d/%m/%Y %H:%M}

        ### Filtro temporal
        O período escolhido na barra lateral é um **filtro global**. Isso significa que os gráficos,
        estatísticas, disponibilidade, qualidade e análises usam somente os registros desse intervalo.

        ### Política de acesso
        A plataforma pode ser usada para visualização científica pública, mas não oferece download
        direto do conjunto bruto. O acesso aos dados depende de autorização do responsável.
        """
    )

# ------------------------------------------------------------
# SOLICITAÇÃO
# ------------------------------------------------------------

elif page == "Solicitar Dados":
    st.header("Solicitar Dados")

    st.warning(
        "Não há download público direto. O fornecimento de dados depende de autorização expressa."
    )

    with st.form("request_form"):
        name = st.text_input("Nome")
        institution = st.text_input("Instituição")
        email = st.text_input("E-mail")
        requested_period = st.text_input(
            "Período solicitado",
            value=f"{start_dt:%d/%m/%Y %H:%M} a {end_dt:%d/%m/%Y %H:%M}",
        )
        variables = st.text_input("Variáveis de interesse")
        purpose = st.text_area("Finalidade científica ou acadêmica")
        agreement = st.checkbox("Declaro que o acesso depende de autorização prévia.")
        submitted = st.form_submit_button("Preparar solicitação")

        if submitted:
            if not name or not email or not purpose or not agreement:
                st.error("Preencha nome, e-mail e finalidade e confirme a declaração.")
            else:
                st.success(
                    "Solicitação preparada. Nesta versão, o formulário ainda não envia nem armazena automaticamente."
                )

st.divider()
st.caption(
    "EcoFlux Brasil • Visualização científica pública • Dados brutos somente mediante autorização"
)
