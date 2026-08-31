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
    .block-container {padding-top: 1.25rem; padding-bottom: 2rem;}
    h1, h2, h3 {letter-spacing: -0.02em;}
    [data-testid="stMetricValue"] {font-size: 1.45rem;}
    </style>
    """,
    unsafe_allow_html=True,
)

EXPECTED_ORIGINAL_VARS = [
    "TIMESTAMP", "Tau", "H", "LE", "co2_flux", "h2o_flux",
    "air_temperature", "RH", "VPD", "wind_speed", "wind_dir",
    "u*", "TKE", "ET", "met_Rg_i_Avg", "met_Rg_r_Avg",
    "met_G_Avg", "met_NET_Avg", "met_T_ar_Avg", "met_UR_ar",
    "met_PPT_Tot", "met_WS_S_WVT", "met_WindDir_D1_WVT"
]

@st.cache_data(show_spinner=False)
def load_original_xlsx(uploaded_file):
    xls = pd.ExcelFile(uploaded_file)
    sheet = xls.sheet_names[0]
    df = pd.read_excel(uploaded_file, sheet_name=sheet)

    # Remove eventual linha de unidades/cabeçalho auxiliar quando TIMESTAMP não for válido.
    df = df.copy()
    df["TIMESTAMP_parsed"] = pd.to_datetime(df["TIMESTAMP"], errors="coerce", dayfirst=False)
    df = df[df["TIMESTAMP_parsed"].notna()].copy()
    df = df.sort_values("TIMESTAMP_parsed")

    # Converte variáveis numéricas quando possível.
    for c in df.columns:
        if c not in ["TIMESTAMP", "TIMESTAMP_parsed", "filename", "date", "time"]:
            df[c] = pd.to_numeric(df[c], errors="coerce")

    return df, sheet

def existing(df, names):
    return [c for c in names if c in df.columns]

def valid_pct(series):
    return 100 * series.notna().mean() if len(series) else np.nan

def aggregate_time(df, variables, resolution):
    variables = existing(df, variables)
    if not variables:
        return pd.DataFrame()

    d = df[["TIMESTAMP_parsed"] + variables].copy().set_index("TIMESTAMP_parsed")

    if resolution == "30 min":
        return d.reset_index()

    rule = {
        "Horário": "1H",
        "Diário": "1D",
        "Semanal": "1W",
        "Mensal": "1MS",
    }[resolution]

    return d.resample(rule).mean(numeric_only=True).reset_index()

def line_chart(df, var, title, resolution, y_title=None):
    if var not in df.columns:
        st.info("Variável não disponível.")
        return

    d = aggregate_time(df, [var], resolution)
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
        height=420,
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

def qc_distribution(df, var):
    s = df[var].astype("string").fillna("NA")
    q = s.value_counts().rename_axis("Código").reset_index(name="Frequência")
    q["Percentual (%)"] = 100 * q["Frequência"] / q["Frequência"].sum()
    fig = px.bar(
        q,
        x="Código",
        y="Frequência",
        text="Percentual (%)",
        title=f"Distribuição dos códigos — {var}",
    )
    fig.update_traces(texttemplate="%{text:.1f}%")
    st.plotly_chart(fig, use_container_width=True)
    st.dataframe(q, use_container_width=True)

st.title("🌱 EcoFlux Brasil")
st.caption("Plataforma de Dados Micrometeorológicos e Fluxos Ecossistêmicos")

st.sidebar.header("Navegação")
page = st.sidebar.radio(
    "Seção",
    [
        "Visão Geral",
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
    help=(
        "Para desenvolvimento. Na versão pública final, os dados deverão ser carregados "
        "automaticamente de uma fonte privada, sem botão de download."
    ),
)

st.sidebar.caption(
    "Política de acesso: visualização pública; dados brutos somente mediante autorização."
)

if uploaded is None:
    st.info(
        "Carregue a planilha original para visualizar o painel. "
        "Na versão pública final, este upload será substituído por carregamento automático protegido."
    )
    st.stop()

try:
    df, sheet_name = load_original_xlsx(uploaded)
except Exception as e:
    st.error(f"Não foi possível ler o arquivo: {e}")
    st.stop()

# Filtros temporais
st.sidebar.subheader("Período")
min_dt = df["TIMESTAMP_parsed"].min()
max_dt = df["TIMESTAMP_parsed"].max()

date_range = st.sidebar.date_input(
    "Intervalo de datas",
    value=(min_dt.date(), max_dt.date()),
    min_value=min_dt.date(),
    max_value=max_dt.date(),
)

filtered = df.copy()
if isinstance(date_range, tuple) and len(date_range) == 2:
    d0, d1 = date_range
    filtered = filtered[
        (filtered["TIMESTAMP_parsed"].dt.date >= d0)
        & (filtered["TIMESTAMP_parsed"].dt.date <= d1)
    ].copy()

resolution = st.sidebar.selectbox(
    "Agregação temporal",
    ["30 min", "Horário", "Diário", "Semanal", "Mensal"],
    index=2,
)

if page == "Visão Geral":
    st.header("Visão Geral")

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Registros", f"{len(filtered):,}".replace(",", "."))
    c2.metric("Variáveis", len([c for c in df.columns if c != "TIMESTAMP_parsed"]))
    c3.metric("Resolução original", "30 min")
    c4.metric("Cobertura temporal", f"{(max_dt - min_dt).days} dias")

    st.markdown(
        f"**Período da série:** {min_dt:%d/%m/%Y %H:%M} — {max_dt:%d/%m/%Y %H:%M}"
    )
    st.caption(f"Aba lida: {sheet_name}")

    matched = len(existing(df, EXPECTED_ORIGINAL_VARS))
    st.info(
        f"Foram reconhecidas {matched} variáveis-chave da estrutura original, "
        "incluindo fluxos, meteorologia, turbulência, QC e variáveis pareadas da estação."
    )

    st.subheader("Disponibilidade das variáveis")
    data_cols = [
        c for c in df.columns
        if c not in ["TIMESTAMP", "TIMESTAMP_parsed", "filename", "date", "time"]
        and pd.api.types.is_numeric_dtype(df[c])
    ]

    availability = pd.DataFrame({
        "Variável": data_cols,
        "Disponibilidade (%)": [valid_pct(filtered[c]) for c in data_cols],
        "Ausentes": [int(filtered[c].isna().sum()) for c in data_cols],
    }).sort_values(["Disponibilidade (%)", "Variável"])

    fig = px.bar(
        availability.head(30),
        x="Disponibilidade (%)",
        y="Variável",
        orientation="h",
        hover_data=["Ausentes"],
        title="30 variáveis com menor disponibilidade",
    )
    fig.update_layout(height=750, yaxis={"categoryorder": "total ascending"})
    st.plotly_chart(fig, use_container_width=True)

    with st.expander("Tabela completa de disponibilidade"):
        st.dataframe(availability, use_container_width=True)

elif page == "Eddy Covariance":
    st.header("Eddy Covariance")

    sections = [
        ("Fluxo de CO₂", ["co2_flux"]),
        ("Fluxo de calor sensível", ["H"]),
        ("Fluxo de calor latente", ["LE"]),
        ("Fluxo de vapor d'água", ["h2o_flux"]),
        ("Fricção / turbulência", ["u*", "TKE"]),
    ]

    for title, opts in sections:
        vars_ok = existing(filtered, opts)
        if not vars_ok:
            continue
        var = st.selectbox(f"Variável — {title}", vars_ok, key=f"ec_{title}")
        line_chart(filtered, var, f"{title}: {var}", resolution)
        stats_cards(filtered, var)

elif page == "Meteorologia":
    st.header("Meteorologia")

    sections = [
        ("Temperatura do ar", ["air_temperature", "met_T_ar_Avg"]),
        ("Umidade relativa", ["RH", "met_UR_ar"]),
        ("VPD", ["VPD"]),
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

elif page == "Balanço de Energia":
    st.header("Balanço de Energia")

    energy_vars = existing(filtered, ["H", "LE", "met_G_Avg", "met_NET_Avg"])
    if not energy_vars:
        st.info("Nenhuma variável de balanço de energia disponível.")
    else:
        for var in energy_vars:
            line_chart(filtered, var, f"Componente do balanço de energia: {var}", resolution)
            stats_cards(filtered, var)

        if all(v in filtered.columns for v in ["H", "LE", "met_G_Avg", "met_NET_Avg"]):
            st.subheader("Fechamento simplificado do balanço de energia")
            d = filtered[["TIMESTAMP_parsed", "H", "LE", "met_G_Avg", "met_NET_Avg"]].dropna()
            if not d.empty:
                d["Disponivel"] = d["met_NET_Avg"] - d["met_G_Avg"]
                d["Turbulento"] = d["H"] + d["LE"]
                fig = px.scatter(
                    d,
                    x="Disponivel",
                    y="Turbulento",
                    opacity=0.4,
                    title="H + LE versus Rn - G",
                )
                st.plotly_chart(fig, use_container_width=True)
                st.caption(
                    "Diagnóstico exploratório. A interpretação do fechamento requer confirmar "
                    "as unidades, convenções de sinal e o significado exato de `met_NET_Avg` e `met_G_Avg`."
                )

elif page == "Água e Evapotranspiração":
    st.header("Água e Evapotranspiração")

    vars_ok = existing(filtered, ["ET", "h2o_flux", "VPD", "met_PPT_Tot"])
    for var in vars_ok:
        line_chart(filtered, var, var, resolution)
        stats_cards(filtered, var)

elif page == "Qualidade dos Dados":
    st.header("Qualidade dos Dados")

    qc_vars = existing(
        filtered,
        [
            "qc_Tau", "qc_H", "qc_LE", "qc_co2_flux",
            "qc_h2o_flux", "qc_ch4_flux",
            "spikes_hf", "drop_out_hf",
            "absolute_limits_hf", "skewness_kurtosis_hf",
            "discontinuities_hf", "timelag_hf",
            "attack_angle_hf", "non_steady_wind_hf"
        ],
    )

    if qc_vars:
        chosen = st.selectbox("Indicador de qualidade", qc_vars)
        qc_distribution(filtered, chosen)

    st.subheader("Cobertura de dados por variável-chave")
    keys = existing(
        filtered,
        [
            "co2_flux", "H", "LE", "h2o_flux", "u*", "TKE",
            "air_temperature", "RH", "VPD", "wind_speed",
            "met_Rg_i_Avg", "met_NET_Avg", "met_PPT_Tot"
        ],
    )
    cov = pd.DataFrame({
        "Variável": keys,
        "Disponibilidade (%)": [valid_pct(filtered[c]) for c in keys],
        "Ausentes": [int(filtered[c].isna().sum()) for c in keys],
    })
    st.dataframe(cov, use_container_width=True)

elif page == "Sobre os Dados":
    st.header("Sobre os Dados")

    st.markdown(
        """
        ### Dados originais
        Esta versão usa a planilha original pareada de **Eddy Covariance + micrometeorologia**.
        O eixo temporal é baseado diretamente em `TIMESTAMP`, sem reconstrução artificial.

        ### Resolução temporal
        A série original possui resolução de **30 minutos**.

        ### Política de acesso
        A plataforma é destinada à **visualização científica pública**.
        Não há download público direto do conjunto bruto.
        Qualquer fornecimento de dados depende de autorização do responsável.

        ### Próxima integração
        Os produtos processados, incluindo NEE tratado, gap-filling, Reco e GPP,
        poderão ser incorporados como uma segunda camada do EcoFlux Brasil.
        """
    )

elif page == "Solicitar Dados":
    st.header("Solicitar Dados")

    st.warning(
        "O conjunto de dados não está disponível para download público. "
        "Solicitações dependem de autorização expressa do responsável."
    )

    with st.form("request_form"):
        name = st.text_input("Nome")
        institution = st.text_input("Instituição")
        email = st.text_input("E-mail")
        variables = st.text_input("Variáveis / período de interesse")
        purpose = st.text_area("Finalidade científica ou acadêmica")
        agreement = st.checkbox(
            "Declaro que o acesso dependerá de autorização prévia."
        )
        submitted = st.form_submit_button("Preparar solicitação")

        if submitted:
            if not name or not email or not purpose or not agreement:
                st.error("Preencha nome, e-mail e finalidade e confirme a declaração.")
            else:
                st.success(
                    "Solicitação preparada. Nesta versão gratuita, "
                    "o formulário ainda não envia nem armazena automaticamente."
                )
                st.text_area(
                    "Resumo",
                    value=(
                        f"Nome: {name}\n"
                        f"Instituição: {institution}\n"
                        f"E-mail: {email}\n"
                        f"Variáveis/período: {variables}\n\n"
                        f"Finalidade:\n{purpose}"
                    ),
                    height=220,
                )

st.divider()
st.caption(
    "EcoFlux Brasil • Visualização científica pública • Dados brutos somente mediante autorização"
)
