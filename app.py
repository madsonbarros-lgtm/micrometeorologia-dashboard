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
# CONFIGURAÇÃO CIENTÍFICA DO CONJUNTO
# ============================================================

FIRST_TIMESTAMP = pd.Timestamp("2025-06-04 20:00:00")
SAMPLING_MINUTES = 30

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

def season_start(value, first_season=False):
    """
    Reconstrói o início de cada bloco.
    O primeiro bloco é ancorado no timestamp informado pelo pesquisador.
    Para os blocos seguintes, o código season fornece ano/mês; o início
    é fixado no primeiro dia daquele mês às 20:00, coerente com a passagem
    dos blocos trimestrais observada no arquivo.
    """
    if first_season:
        return FIRST_TIMESTAMP

    s = str(int(float(value))).zfill(7)
    year = int(s[:4])
    month = int(s[-3:])
    return pd.Timestamp(year=year, month=month, day=1, hour=20, minute=0)

@st.cache_data(show_spinner=False)
def load_xlsx(uploaded_file):
    xls = pd.ExcelFile(uploaded_file)
    sheet = xls.sheet_names[0]
    df = pd.read_excel(uploaded_file, sheet_name=sheet)
    df = df.copy()

    for c in df.columns:
        if c != "season":
            df[c] = pd.to_numeric(df[c], errors="coerce")

    # Preserva a ordem original dos blocos.
    unique_seasons = list(pd.unique(df["season"].dropna()))
    parts = []

    for i, season in enumerate(unique_seasons):
        part = df[df["season"] == season].copy()
        start = season_start(season, first_season=(i == 0))
        part["datetime"] = pd.date_range(
            start=start,
            periods=len(part),
            freq=f"{SAMPLING_MINUTES}min"
        )
        part["season_label"] = season_label(season)
        parts.append(part)

    out = pd.concat(parts, ignore_index=True)
    out["_obs"] = np.arange(1, len(out) + 1)
    return out, sheet

def existing(df, names):
    return [c for c in names if c in df.columns]

def valid_pct(s):
    return 100 * s.notna().mean() if len(s) else np.nan

def aggregate_time(df, variables, resolution):
    use = ["datetime"] + variables
    d = df[use].copy().set_index("datetime")

    if resolution == "30 min":
        return d.reset_index()

    rule = {
        "Diário": "D",
        "Semanal": "W",
        "Mensal": "MS",
    }[resolution]

    return d.resample(rule).mean(numeric_only=True).reset_index()

def line_chart(df, variables, title, resolution="30 min"):
    variables = existing(df, variables)
    if not variables:
        st.info("Nenhuma variável compatível está disponível.")
        return

    d = aggregate_time(df, variables, resolution)

    fig = go.Figure()
    for var in variables:
        fig.add_trace(
            go.Scattergl(
                x=d["datetime"],
                y=d[var],
                mode="lines",
                name=var,
                connectgaps=False,
            )
        )

    fig.update_layout(
        title=title,
        xaxis_title="Data e hora",
        yaxis_title="Valor",
        hovermode="x unified",
        height=510,
        margin=dict(l=20, r=20, t=55, b=20),
        legend_title="Variável",
    )
    st.plotly_chart(fig, use_container_width=True)

def stats_table(df, variables):
    variables = existing(df, variables)
    if not variables:
        return

    d = df[variables].describe().T
    d["Disponibilidade (%)"] = [valid_pct(df[v]) for v in variables]
    st.dataframe(d, use_container_width=True)

# ============================================================
# CABEÇALHO / NAVEGAÇÃO
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
        "O XLSX permanece apenas na sessão. "
        "O aplicativo não oferece botão de download do conjunto bruto."
    ),
)

st.sidebar.caption(
    "Política de acesso: visualização permitida; fornecimento do conjunto "
    "de dados somente mediante autorização do responsável."
)

if uploaded is None:
    st.info(
        "Carregue o XLSX para validar a plataforma. "
        "Na publicação definitiva, a fonte de dados deverá ficar em armazenamento privado."
    )
    st.warning(
        "Importante: não coloque o XLSX bruto em um repositório público do GitHub."
    )
    st.stop()

try:
    df, sheet_name = load_xlsx(uploaded)
except Exception as e:
    st.error(f"Não foi possível ler o arquivo: {e}")
    st.stop()

# ============================================================
# FILTROS
# ============================================================

season_options = list(pd.unique(df["season_label"]))
selected_seasons = st.sidebar.multiselect(
    "Período (season)",
    options=season_options,
    default=season_options,
)

filtered = df[df["season_label"].isin(selected_seasons)].copy()

if not filtered.empty:
    min_dt = filtered["datetime"].min().to_pydatetime()
    max_dt = filtered["datetime"].max().to_pydatetime()

    date_range = st.sidebar.date_input(
        "Intervalo de datas",
        value=(min_dt.date(), max_dt.date()),
        min_value=min_dt.date(),
        max_value=max_dt.date(),
    )

    if isinstance(date_range, tuple) and len(date_range) == 2:
        start_date, end_date = date_range
        filtered = filtered[
            (filtered["datetime"].dt.date >= start_date)
            & (filtered["datetime"].dt.date <= end_date)
        ]

resolution = st.sidebar.selectbox(
    "Resolução dos gráficos",
    ["30 min", "Diário", "Semanal", "Mensal"],
    index=1,
)

# ============================================================
# PÁGINAS
# ============================================================

if page == "Visão Geral":
    st.header("Visão Geral")

    matched = len(set(EXPECTED_COLUMNS).intersection(df.columns))
    compatibility = 100 * matched / len(EXPECTED_COLUMNS)

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Registros exibidos", f"{len(filtered):,}".replace(",", "."))
    c2.metric("Variáveis originais", len([c for c in df.columns if c not in ["datetime", "season_label", "_obs"]]))
    c3.metric("Resolução original", "30 min")
    c4.metric("Compatibilidade", f"{compatibility:.0f}%")

    if not filtered.empty:
        st.markdown(
            f"**Intervalo reconstruído na seleção:** "
            f"{filtered['datetime'].min():%d/%m/%Y %H:%M} — "
            f"{filtered['datetime'].max():%d/%m/%Y %H:%M}"
        )

    st.caption(f"Aba lida: {sheet_name}")

    st.info(
        "O eixo temporal é reconstruído em intervalos de 30 minutos dentro de cada "
        "bloco `season`. O primeiro bloco é ancorado em 04/06/2025 20:00."
    )

    # Diagnóstico da coerência dos blocos
    block_summary = (
        df.groupby(["season", "season_label"], sort=False)
        .agg(
            Registros=("datetime", "size"),
            Inicio=("datetime", "min"),
            Fim=("datetime", "max"),
        )
        .reset_index()
    )
    block_summary["Dias_equivalentes"] = block_summary["Registros"] / 48.0

    st.subheader("Blocos temporais reconstruídos")
    st.dataframe(block_summary, use_container_width=True)

    st.subheader("Disponibilidade das variáveis")
    data_cols = [
        c for c in df.columns
        if c not in ["season", "season_label", "datetime", "_obs"]
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

elif page == "Meteorologia":
    st.header("Meteorologia")

    aux = existing(
        filtered,
        [
            "Rg_orig", "Rg_f", "Rg_fall",
            "Tair_orig", "Tair_f", "Tair_fall",
            "VPD_orig", "VPD_f", "VPD_fall",
            "PotRad_NEW", "FP_Temp_NEW", "NEW_FP_Temp", "NEW_FP_VPD"
        ]
    )

    selected = st.multiselect(
        "Variáveis",
        options=aux,
        default=existing(filtered, MET_VARS),
    )

    line_chart(
        filtered,
        selected,
        f"Variáveis meteorológicas — resolução: {resolution}",
        resolution,
    )
    stats_table(filtered, selected)

    st.caption(
        "As unidades serão exibidas no eixo somente após validação do dicionário "
        "de metadados do processamento."
    )

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
        "Variáveis",
        options=options,
        default=existing(filtered, CARBON_VARS),
    )

    line_chart(
        filtered,
        selected,
        f"NEE, Reco e GPP — resolução: {resolution}",
        resolution,
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
            st.metric("Correlação de Pearson (r)", f"{dxy[xvar].corr(dxy[yvar]):.3f}")

elif page == "Qualidade e Gap-filling":
    st.header("Qualidade e Gap-filling")

    st.info(
        "Os códigos originais de QC são preservados. A interpretação de cada classe "
        "deve seguir a documentação do processamento utilizado."
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
        st.subheader("Diagnósticos de preenchimento")
        chosen_gap = st.multiselect(
            "Variáveis de gap-filling",
            options=gap,
            default=gap[:4],
        )
        stats_table(filtered, chosen_gap)

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

    line_chart(
        filtered,
        selected,
        f"Produtos de particionamento — resolução: {resolution}",
        resolution,
    )
    stats_table(filtered, selected)

elif page == "Sobre os Dados":
    st.header("Sobre os Dados")

    st.markdown(
        """
        ### Política de acesso

        Esta plataforma é destinada à **visualização científica pública**.
        O conjunto de dados bruto não é oferecido para download direto.
        Solicitações de acesso aos dados devem ser avaliadas e autorizadas
        pelo responsável pela plataforma.

        ### Resolução temporal

        As observações possuem resolução original de **30 minutos**.
        A coluna `season` codifica **ano e mês** do bloco de processamento.

        ### Transparência metodológica

        O aplicativo não atribui unidades ou interpreta códigos QC sem
        documentação de metadados. Esse dicionário poderá ser incorporado
        posteriormente para tornar a plataforma autoexplicativa.
        """
    )

    schema = pd.DataFrame({
        "Variável": [c for c in df.columns if c not in ["datetime", "season_label", "_obs"]],
        "Tipo": [str(df[c].dtype) for c in df.columns if c not in ["datetime", "season_label", "_obs"]],
        "Ausentes": [int(df[c].isna().sum()) for c in df.columns if c not in ["datetime", "season_label", "_obs"]],
        "Disponibilidade (%)": [valid_pct(df[c]) for c in df.columns if c not in ["datetime", "season_label", "_obs"]],
    })
    st.dataframe(schema, use_container_width=True)

elif page == "Solicitar Dados":
    st.header("Solicitar Dados")

    st.warning(
        "Não existe download público direto. O fornecimento dos dados depende "
        "de autorização do responsável pela plataforma."
    )

    with st.form("request_form"):
        name = st.text_input("Nome")
        institution = st.text_input("Instituição")
        email = st.text_input("E-mail")
        variables = st.text_input("Variáveis / período de interesse")
        purpose = st.text_area("Finalidade científica ou acadêmica")
        agreement = st.checkbox(
            "Declaro que a utilização dos dados dependerá de autorização prévia."
        )
        submitted = st.form_submit_button("Preparar solicitação")

        if submitted:
            if not name or not email or not purpose or not agreement:
                st.error(
                    "Preencha nome, e-mail e finalidade e confirme a declaração de autorização."
                )
            else:
                st.success(
                    "Solicitação preparada. Nesta versão gratuita inicial, "
                    "o formulário ainda não envia nem armazena a solicitação automaticamente."
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
    "EcoFlux Brasil • Visualização científica pública • "
    "Dados brutos somente mediante autorização"
)
