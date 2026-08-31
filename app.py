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
    .block-container {padding-top: 1.4rem; padding-bottom: 2rem;}
    h1, h2, h3 {letter-spacing: -0.02em;}
    [data-testid="stMetricValue"] {font-size: 1.5rem;}
    </style>
    """,
    unsafe_allow_html=True,
)

# ============================================================
# METADADOS CONHECIDOS
# ============================================================

SAMPLING_MINUTES = 30
FIRST_OBSERVED_TIMESTAMP = pd.Timestamp("2025-06-04 20:00:00")

EXPECTED_COLUMNS = [
    "season",
    "NEE_orig", "NEE_f", "NEE_fqc", "NEE_fall", "NEE_fall_qc",
    "NEE_fnum", "NEE_fsd", "NEE_fmeth", "NEE_fwin",
    "Rg_orig", "Rg_f", "Rg_fqc", "Rg_fall", "Rg_fall_qc",
    "Rg_fnum", "Rg_fsd", "Rg_fmeth", "Rg_fwin",
    "Tair_orig", "Tair_f", "Tair_fqc", "Tair_fall", "Tair_fall_qc",
    "Tair_fnum", "Tair_fsd", "Tair_fmeth", "Tair_fwin",
    "VPD_orig", "VPD_f", "VPD_fqc", "VPD_fall", "VPD_fall_qc",
    "VPD_fnum", "VPD_fsd", "VPD_fmeth", "VPD_fwin",
    "PotRad_NEW", "FP_Temp_NEW", "E_0_NEW", "FP_VARnight", "FP_VARday",
    "NEW_FP_Temp", "NEW_FP_VPD", "FP_RRef_Night", "FP_qc", "FP_dRecPar",
    "FP_errorcode", "FP_GPP2000", "FP_k", "FP_beta", "FP_alpha",
    "FP_RRef", "FP_E0", "FP_k_sd", "FP_beta_sd", "FP_alpha_sd",
    "FP_RRef_sd", "FP_E0_sd", "Reco_DT", "GPP_DT", "Reco_DT_SD", "GPP_DT_SD"
]

MET_VARS = ["Rg_fall", "Tair_fall", "VPD_fall"]
CARBON_VARS = ["NEE_fall", "Reco_DT", "GPP_DT"]

QC_VARS = [
    "NEE_fqc", "NEE_fall_qc",
    "Rg_fqc", "Rg_fall_qc",
    "Tair_fqc", "Tair_fall_qc",
    "VPD_fqc", "VPD_fall_qc",
    "FP_qc", "FP_errorcode"
]

GAP_VARS = [
    "NEE_fnum", "NEE_fmeth", "NEE_fwin", "NEE_fsd",
    "Rg_fnum", "Rg_fmeth", "Rg_fwin", "Rg_fsd",
    "Tair_fnum", "Tair_fmeth", "Tair_fwin", "Tair_fsd",
    "VPD_fnum", "VPD_fmeth", "VPD_fwin", "VPD_fsd",
]

def season_label(value):
    try:
        s = str(int(float(value))).zfill(7)
        year = int(s[:4])
        month = int(s[-3:])
        months = [
            "Jan", "Fev", "Mar", "Abr", "Mai", "Jun",
            "Jul", "Ago", "Set", "Out", "Nov", "Dez"
        ]
        if 1 <= month <= 12:
            return f"{months[month-1]}/{year}"
    except Exception:
        pass
    return str(value)

@st.cache_data(show_spinner=False)
def load_xlsx(uploaded_file):
    xls = pd.ExcelFile(uploaded_file)
    sheet = xls.sheet_names[0]
    df = pd.read_excel(uploaded_file, sheet_name=sheet)
    df = df.copy()

    for c in df.columns:
        if c != "season":
            df[c] = pd.to_numeric(df[c], errors="coerce")

    # Mantém a ordem original de aquisição dentro de cada bloco season.
    df["season_label"] = df["season"].apply(season_label)
    df["_global_obs"] = np.arange(1, len(df) + 1)

    # Índice local de 30 min dentro de cada bloco.
    df["_season_obs"] = df.groupby("season", sort=False).cumcount()
    df["elapsed_hours"] = df["_season_obs"] * (SAMPLING_MINUTES / 60.0)
    df["elapsed_days"] = df["elapsed_hours"] / 24.0

    # Somente o primeiro bloco possui timestamp absoluto conhecido.
    first_season = pd.unique(df["season"].dropna())[0]
    mask = df["season"] == first_season
    df["known_datetime"] = pd.NaT
    df.loc[mask, "known_datetime"] = (
        FIRST_OBSERVED_TIMESTAMP
        + pd.to_timedelta(df.loc[mask, "_season_obs"] * SAMPLING_MINUTES, unit="min")
    )

    return df, sheet

def existing(df, names):
    return [c for c in names if c in df.columns]

def valid_pct(series):
    return 100 * series.notna().mean() if len(series) else np.nan

def stats_table(df, variables):
    variables = existing(df, variables)
    if not variables:
        return
    out = df[variables].describe().T
    out["Disponibilidade (%)"] = [valid_pct(df[v]) for v in variables]
    st.dataframe(out, use_container_width=True)

def line_chart_relative(df, variables, title, x_mode):
    variables = existing(df, variables)
    if not variables:
        st.info("Nenhuma variável compatível está disponível.")
        return

    fig = go.Figure()

    for season_name in pd.unique(df["season_label"]):
        part = df[df["season_label"] == season_name].copy()

        if x_mode == "Tempo relativo (dias)":
            x = part["elapsed_days"]
            x_title = "Tempo relativo dentro do bloco (dias)"
        elif x_mode == "Tempo relativo (horas)":
            x = part["elapsed_hours"]
            x_title = "Tempo relativo dentro do bloco (horas)"
        else:
            x = part["_season_obs"] + 1
            x_title = "Índice sequencial dentro do bloco"

        for var in variables:
            fig.add_trace(
                go.Scattergl(
                    x=x,
                    y=part[var],
                    mode="lines",
                    name=f"{var} — {season_name}",
                    connectgaps=False,
                )
            )

    fig.update_layout(
        title=title,
        xaxis_title=x_title,
        yaxis_title="Valor",
        hovermode="x unified",
        height=520,
        margin=dict(l=20, r=20, t=55, b=20),
        legend_title="Variável / season",
    )
    st.plotly_chart(fig, use_container_width=True)

# ============================================================
# CABEÇALHO E NAVEGAÇÃO
# ============================================================

st.title("🌱 EcoFlux Brasil")
st.caption("Plataforma de Dados Micrometeorológicos e Fluxos Ecossistêmicos")

st.sidebar.header("Navegação")
page = st.sidebar.radio(
    "Seção",
    [
        "Visão Geral",
        "Meteorologia",
        "Fluxos de Carbono",
        "Qualidade e Gap-filling",
        "Particionamento de Carbono",
        "Sobre os Dados",
        "Solicitar Dados",
    ],
)

st.sidebar.divider()
st.sidebar.subheader("Fonte de dados")

uploaded = st.sidebar.file_uploader(
    "Carregar XLSX para esta sessão",
    type=["xlsx"],
    help=(
        "O arquivo é usado apenas para visualização nesta sessão. "
        "O aplicativo não oferece download público do conjunto bruto."
    ),
)

st.sidebar.caption(
    "Política de acesso: visualização pública permitida; "
    "fornecimento dos dados somente mediante autorização do responsável."
)

if uploaded is None:
    st.info(
        "Carregue o XLSX para visualizar os dados. "
        "Na versão pública definitiva, a fonte de dados deverá permanecer privada."
    )
    st.warning(
        "Não coloque o XLSX bruto em um repositório público do GitHub."
    )
    st.stop()

try:
    df, sheet_name = load_xlsx(uploaded)
except Exception as e:
    st.error(f"Não foi possível ler o arquivo XLSX: {e}")
    st.stop()

season_options = list(pd.unique(df["season_label"]))
selected_seasons = st.sidebar.multiselect(
    "Período (season)",
    options=season_options,
    default=season_options,
)

filtered = df[df["season_label"].isin(selected_seasons)].copy()

x_mode = st.sidebar.selectbox(
    "Eixo horizontal",
    [
        "Tempo relativo (dias)",
        "Tempo relativo (horas)",
        "Índice sequencial",
    ],
)

# ============================================================
# VISÃO GERAL
# ============================================================

if page == "Visão Geral":
    st.header("Visão Geral")

    matched = len(set(EXPECTED_COLUMNS).intersection(df.columns))
    compatibility = 100 * matched / len(EXPECTED_COLUMNS)

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Registros exibidos", f"{len(filtered):,}".replace(",", "."))
    c2.metric(
        "Variáveis originais",
        len([c for c in df.columns if not c.startswith("_") and c not in ["season_label", "elapsed_hours", "elapsed_days", "known_datetime"]])
    )
    c3.metric("Resolução original", "30 min")
    c4.metric("Compatibilidade", f"{compatibility:.0f}%")

    st.caption(f"Aba lida: {sheet_name}")

    st.warning(
        "Esta versão NÃO reconstrói datas absolutas para os blocos sem timestamp documentado. "
        "A coluna `season` é usada apenas como ano/mês e os gráficos utilizam tempo relativo "
        "dentro de cada bloco. Isso evita apresentar datas artificiais como observações reais."
    )

    st.info(
        "Timestamp absoluto confirmado apenas para o início do primeiro bloco: "
        "04/06/2025 20:00. A resolução informada é de 30 minutos e a sequência dentro "
        "de cada bloco é contínua."
    )

    block_summary = (
        df.groupby(["season", "season_label"], sort=False)
        .agg(
            Registros=("_season_obs", "size"),
            Duracao_dias=("elapsed_days", "max"),
            Dados_validos_NEE=("NEE_fall", lambda x: int(x.notna().sum())) if "NEE_fall" in df.columns else ("_season_obs", "size"),
        )
        .reset_index()
    )

    block_summary["Duracao_dias"] = block_summary["Duracao_dias"] + (SAMPLING_MINUTES / 60 / 24)

    st.subheader("Blocos observacionais")
    st.dataframe(block_summary, use_container_width=True)

    # Primeiro bloco: intervalo absoluto conhecido.
    first_season = pd.unique(df["season"].dropna())[0]
    first_part = df[df["season"] == first_season]
    if first_part["known_datetime"].notna().any():
        st.markdown(
            f"**Primeiro bloco com timestamp conhecido:** "
            f"{first_part['known_datetime'].min():%d/%m/%Y %H:%M} até "
            f"{first_part['known_datetime'].max():%d/%m/%Y %H:%M}."
        )

    st.subheader("Disponibilidade das variáveis")
    data_cols = [
        c for c in df.columns
        if c not in [
            "season", "season_label", "_global_obs", "_season_obs",
            "elapsed_hours", "elapsed_days", "known_datetime"
        ]
    ]

    availability = pd.DataFrame({
        "Variável": data_cols,
        "Disponibilidade (%)": [valid_pct(filtered[c]) for c in data_cols],
        "Ausentes": [int(filtered[c].isna().sum()) for c in data_cols],
    }).sort_values(["Disponibilidade (%)", "Variável"])

    fig = px.bar(
        availability.head(25),
        x="Disponibilidade (%)",
        y="Variável",
        orientation="h",
        hover_data=["Ausentes"],
        title="25 variáveis com menor disponibilidade",
    )
    fig.update_layout(height=650, yaxis={"categoryorder": "total ascending"})
    st.plotly_chart(fig, use_container_width=True)

    with st.expander("Tabela completa de disponibilidade"):
        st.dataframe(availability, use_container_width=True)

# ============================================================
# METEOROLOGIA
# ============================================================

elif page == "Meteorologia":
    st.header("Meteorologia")

    options = existing(
        filtered,
        [
            "Rg_orig", "Rg_f", "Rg_fall",
            "Tair_orig", "Tair_f", "Tair_fall",
            "VPD_orig", "VPD_f", "VPD_fall",
            "PotRad_NEW", "FP_Temp_NEW", "NEW_FP_Temp", "NEW_FP_VPD"
        ],
    )

    selected = st.multiselect(
        "Variáveis meteorológicas",
        options=options,
        default=existing(filtered, MET_VARS),
    )

    line_chart_relative(
        filtered,
        selected,
        "Variáveis meteorológicas por bloco `season`",
        x_mode,
    )
    stats_table(filtered, selected)

    st.caption(
        "As unidades ainda não são exibidas porque devem ser confirmadas no dicionário de metadados."
    )

# ============================================================
# FLUXOS DE CARBONO
# ============================================================

elif page == "Fluxos de Carbono":
    st.header("Fluxos de Carbono")

    options = existing(
        filtered,
        [
            "NEE_orig", "NEE_f", "NEE_fall", "NEE_fsd",
            "Reco_DT", "GPP_DT", "Reco_DT_SD", "GPP_DT_SD"
        ],
    )

    selected = st.multiselect(
        "Variáveis de carbono",
        options=options,
        default=existing(filtered, CARBON_VARS),
    )

    line_chart_relative(
        filtered,
        selected,
        "NEE, Reco e GPP por bloco `season`",
        x_mode,
    )
    stats_table(filtered, selected)

    if len(selected) >= 2:
        st.subheader("Relação entre variáveis")
        c1, c2 = st.columns(2)
        xvar = c1.selectbox("Eixo X", selected, index=0)
        yvar = c2.selectbox("Eixo Y", selected, index=1)

        dxy = filtered[[xvar, yvar]].dropna()
        fig = px.scatter(
            dxy,
            x=xvar,
            y=yvar,
            opacity=0.45,
            title=f"{yvar} × {xvar}",
        )
        st.plotly_chart(fig, use_container_width=True)

        if len(dxy) >= 3:
            st.metric(
                "Correlação de Pearson (r)",
                f"{dxy[xvar].corr(dxy[yvar]):.3f}"
            )

# ============================================================
# QUALIDADE E GAP-FILLING
# ============================================================

elif page == "Qualidade e Gap-filling":
    st.header("Qualidade e Gap-filling")

    st.info(
        "Os códigos originais são preservados. O significado de cada código QC deve ser "
        "confirmado pela documentação do processamento antes de ser descrito ao público."
    )

    qc = existing(filtered, QC_VARS)
    gap = existing(filtered, GAP_VARS)

    if qc:
        chosen = st.selectbox("Flag / código de qualidade", qc)

        q = (
            filtered[chosen]
            .astype("string")
            .fillna("NA")
            .value_counts()
            .rename_axis("Código")
            .reset_index(name="Frequência")
        )
        q["Percentual (%)"] = 100 * q["Frequência"] / q["Frequência"].sum()

        fig = px.bar(
            q,
            x="Código",
            y="Frequência",
            text="Percentual (%)",
            title=f"Distribuição dos códigos — {chosen}",
        )
        fig.update_traces(texttemplate="%{text:.1f}%")
        st.plotly_chart(fig, use_container_width=True)
        st.dataframe(q, use_container_width=True)

    if gap:
        st.subheader("Diagnósticos de gap-filling")
        chosen_gap = st.multiselect(
            "Variáveis diagnósticas",
            options=gap,
            default=gap[:4],
        )
        stats_table(filtered, chosen_gap)

# ============================================================
# PARTICIONAMENTO
# ============================================================

elif page == "Particionamento de Carbono":
    st.header("Particionamento de Carbono")

    options = existing(
        filtered,
        [
            "Reco_DT", "GPP_DT", "Reco_DT_SD", "GPP_DT_SD",
            "FP_Temp_NEW", "E_0_NEW", "FP_VARnight", "FP_VARday",
            "NEW_FP_Temp", "NEW_FP_VPD", "FP_RRef_Night",
            "FP_qc", "FP_dRecPar", "FP_errorcode", "FP_GPP2000",
            "FP_k", "FP_beta", "FP_alpha", "FP_RRef", "FP_E0",
            "FP_k_sd", "FP_beta_sd", "FP_alpha_sd", "FP_RRef_sd", "FP_E0_sd",
        ],
    )

    selected = st.multiselect(
        "Produtos / parâmetros",
        options=options,
        default=existing(filtered, ["Reco_DT", "GPP_DT", "Reco_DT_SD", "GPP_DT_SD"]),
    )

    line_chart_relative(
        filtered,
        selected,
        "Produtos de particionamento por bloco `season`",
        x_mode,
    )
    stats_table(filtered, selected)

# ============================================================
# SOBRE OS DADOS
# ============================================================

elif page == "Sobre os Dados":
    st.header("Sobre os Dados")

    st.markdown(
        """
        ### Política de acesso

        Esta plataforma é destinada à **visualização científica pública**.
        O conjunto bruto não é oferecido para download direto.
        Solicitações de acesso devem ser avaliadas e autorizadas pelo responsável.

        ### Estrutura temporal

        A resolução original informada é de **30 minutos** e os registros seguem
        continuamente dentro de cada bloco `season`. A coluna `season` codifica
        **ano e mês**, mas não fornece sozinha uma data-hora para cada linha.

        Por esse motivo, esta versão usa **tempo relativo dentro de cada bloco**.
        Apenas o primeiro timestamp, **04/06/2025 20:00**, é tratado como data-hora
        absoluta confirmada.

        ### Transparência

        O aplicativo evita criar datas ou unidades não documentadas. Isso mantém
        a interpretação dos gráficos consistente com os metadados realmente disponíveis.
        """
    )

    schema = pd.DataFrame({
        "Variável": [
            c for c in df.columns
            if c not in [
                "season_label", "_global_obs", "_season_obs",
                "elapsed_hours", "elapsed_days", "known_datetime"
            ]
        ],
        "Tipo": [
            str(df[c].dtype) for c in df.columns
            if c not in [
                "season_label", "_global_obs", "_season_obs",
                "elapsed_hours", "elapsed_days", "known_datetime"
            ]
        ],
        "Ausentes": [
            int(df[c].isna().sum()) for c in df.columns
            if c not in [
                "season_label", "_global_obs", "_season_obs",
                "elapsed_hours", "elapsed_days", "known_datetime"
            ]
        ],
    })
    st.dataframe(schema, use_container_width=True)

# ============================================================
# SOLICITAÇÃO DE DADOS
# ============================================================

elif page == "Solicitar Dados":
    st.header("Solicitar Dados")

    st.warning(
        "Não há download público direto. O fornecimento dos dados depende "
        "de autorização expressa do responsável pela plataforma."
    )

    with st.form("request_form"):
        name = st.text_input("Nome")
        institution = st.text_input("Instituição")
        email = st.text_input("E-mail")
        variables = st.text_input("Variáveis / período de interesse")
        purpose = st.text_area("Finalidade científica ou acadêmica")
        agreement = st.checkbox(
            "Declaro que o acesso aos dados dependerá de autorização prévia."
        )
        submitted = st.form_submit_button("Preparar solicitação")

        if submitted:
            if not name or not email or not purpose or not agreement:
                st.error(
                    "Preencha nome, e-mail e finalidade e confirme a declaração."
                )
            else:
                st.success(
                    "Solicitação preparada. Nesta versão gratuita, "
                    "o formulário ainda não envia nem armazena automaticamente."
                )
                st.text_area(
                    "Resumo da solicitação",
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
    "EcoFlux Brasil • Visualização científica pública • "
    "Dados brutos somente mediante autorização"
)
