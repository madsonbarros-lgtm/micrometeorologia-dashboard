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
    .block-container {padding-top: 1.5rem; padding-bottom: 2rem;}
    h1, h2, h3 {letter-spacing: -0.02em;}
    [data-testid="stMetricValue"] {font-size: 1.55rem;}
    .ecoflux-note {
        padding: .75rem 1rem;
        border: 1px solid rgba(128,128,128,.22);
        border-radius: .5rem;
        margin: .25rem 0 1rem 0;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# ============================================================
# Estrutura conhecida do arquivo dados_Uisa_FINAL_CORRIGIDO_V2
# ============================================================

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

CARBON_MAIN = ["NEE_fall", "Reco_DT", "GPP_DT"]
CARBON_AUX = [
    "NEE_orig", "NEE_f", "NEE_fsd",
    "Reco_DT_SD", "GPP_DT_SD", "FP_GPP2000",
    "FP_RRef", "FP_RRef_Night", "FP_E0", "E_0_NEW"
]
MET_MAIN = ["Rg_fall", "Tair_fall", "VPD_fall"]
MET_AUX = [
    "Rg_orig", "Rg_f", "Rg_fsd",
    "Tair_orig", "Tair_f", "Tair_fsd",
    "VPD_orig", "VPD_f", "VPD_fsd",
    "PotRad_NEW", "FP_Temp_NEW", "NEW_FP_Temp", "NEW_FP_VPD"
]
QC_COLUMNS = [
    "NEE_fqc", "NEE_fall_qc",
    "Rg_fqc", "Rg_fall_qc",
    "Tair_fqc", "Tair_fall_qc",
    "VPD_fqc", "VPD_fall_qc",
    "FP_qc", "FP_errorcode"
]
GAPFILL_DIAGNOSTICS = [
    "NEE_fnum", "NEE_fmeth", "NEE_fwin", "NEE_fsd",
    "Rg_fnum", "Rg_fmeth", "Rg_fwin", "Rg_fsd",
    "Tair_fnum", "Tair_fmeth", "Tair_fwin", "Tair_fsd",
    "VPD_fnum", "VPD_fmeth", "VPD_fwin", "VPD_fsd",
]

# O XLSX não contém coluna explícita de data-hora.
# A coluna 'season' é mantida como identificador de período de processamento.
# O eixo temporal usa a ordem original das observações, sem inventar timestamps.

@st.cache_data(show_spinner=False)
def load_xlsx(uploaded_file):
    xls = pd.ExcelFile(uploaded_file)
    sheet = xls.sheet_names[0]
    df = pd.read_excel(uploaded_file, sheet_name=sheet)

    # Preserva ordem original e cria índice de observação.
    df = df.copy()
    df["_obs"] = np.arange(1, len(df) + 1)

    # Converte colunas numéricas quando possível, preservando season como rótulo.
    for c in df.columns:
        if c not in ["season", "_obs"]:
            df[c] = pd.to_numeric(df[c], errors="coerce")

    if "season" in df.columns:
        df["season"] = df["season"].astype("string")

    return df, sheet

def existing(df, names):
    return [c for c in names if c in df.columns]

def valid_percent(series):
    return 100.0 * series.notna().mean() if len(series) else np.nan

def make_line_chart(data, variables, title, y_title="Valor"):
    vars_ok = [v for v in variables if v in data.columns]
    if not vars_ok:
        st.info("Nenhuma variável compatível está disponível nesta seção.")
        return

    fig = go.Figure()
    for var in vars_ok:
        fig.add_trace(
            go.Scattergl(
                x=data["_obs"],
                y=data[var],
                mode="lines",
                name=var,
                connectgaps=False,
            )
        )

    fig.update_layout(
        title=title,
        xaxis_title="Índice sequencial da observação",
        yaxis_title=y_title,
        hovermode="x unified",
        height=500,
        margin=dict(l=20, r=20, t=55, b=20),
        legend_title="Variável",
    )
    st.plotly_chart(fig, use_container_width=True)

def stats_table(data, variables):
    vars_ok = [v for v in variables if v in data.columns]
    if not vars_ok:
        return
    d = data[vars_ok].describe().T
    d["Disponibilidade (%)"] = [valid_percent(data[v]) for v in vars_ok]
    cols = [
        c for c in
        ["count", "mean", "std", "min", "25%", "50%", "75%", "max", "Disponibilidade (%)"]
        if c in d.columns
    ]
    st.dataframe(d[cols], use_container_width=True)

def season_counts(df):
    if "season" not in df.columns:
        return pd.DataFrame()
    out = (
        df.groupby("season", dropna=False)
        .size()
        .rename("Registros")
        .reset_index()
    )
    return out

def filter_by_season(df, selected):
    if "season" not in df.columns or not selected:
        return df
    return df[df["season"].isin(selected)].copy()

# ============================================================
# Interface
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
    help="O arquivo é usado apenas na sessão do aplicativo e não é oferecido para download.",
)

if uploaded is None:
    st.info(
        "Carregue o arquivo XLSX na barra lateral para visualizar os dados. "
        "O arquivo não é publicado pelo aplicativo nem é disponibilizado para download."
    )
    st.markdown(
        """
        ### Estrutura desta versão
        - **Visão Geral:** número de registros, variáveis, períodos `season` e disponibilidade.
        - **Meteorologia:** Rg, Tair, VPD e produtos associados.
        - **Fluxos de Carbono:** NEE, Reco e GPP.
        - **Qualidade e Gap-filling:** flags, métodos e diagnósticos de preenchimento.
        - **Particionamento de Carbono:** parâmetros e produtos associados ao particionamento.
        - **Solicitar Dados:** fluxo de solicitação sem download público direto.
        """
    )
    st.stop()

try:
    df, sheet_name = load_xlsx(uploaded)
except Exception as e:
    st.error(f"Não foi possível ler o XLSX: {e}")
    st.stop()

# ============================================================
# Diagnóstico estrutural
# ============================================================

known_matches = len(set(EXPECTED_COLUMNS).intersection(df.columns))
structure_match = 100 * known_matches / len(EXPECTED_COLUMNS)

if "season" in df.columns:
    seasons = [x for x in df["season"].dropna().unique().tolist()]
    selected_seasons = st.sidebar.multiselect(
        "Período (season)",
        options=seasons,
        default=seasons,
        help=(
            "A coluna 'season' existe no arquivo, mas não é uma coluna de data-hora. "
            "Ela é usada aqui apenas como identificador de período."
        ),
    )
else:
    selected_seasons = []

filtered = filter_by_season(df, selected_seasons)

st.sidebar.caption(
    "Importante: este XLSX não contém uma coluna explícita de data-hora. "
    "Os gráficos usam a ordem sequencial dos registros."
)

# ============================================================
# Páginas
# ============================================================

if page == "Visão Geral":
    st.header("Visão Geral")

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Registros", f"{len(filtered):,}".replace(",", "."))
    c2.metric("Variáveis no XLSX", len([c for c in df.columns if c != "_obs"]))
    c3.metric("Períodos season", df["season"].nunique() if "season" in df.columns else "—")
    c4.metric("Compatibilidade estrutural", f"{structure_match:.0f}%")

    st.caption(f"Aba lida: {sheet_name}")

    st.warning(
        "O arquivo contém a coluna `season`, mas não contém uma coluna explícita de data-hora. "
        "Por rigor científico, esta versão não inventa datas para os 14.544 registros. "
        "Os gráficos usam o índice sequencial das observações. Se houver um arquivo original "
        "com timestamp, podemos incorporá-lo na próxima versão."
    )

    if "season" in df.columns:
        st.subheader("Distribuição dos registros por `season`")
        sc = season_counts(filtered)
        fig = px.bar(
            sc,
            x="season",
            y="Registros",
            text="Registros",
            title="Número de registros em cada identificador de período",
        )
        st.plotly_chart(fig, use_container_width=True)

    st.subheader("Disponibilidade das variáveis")
    data_cols = [c for c in df.columns if c not in ["_obs", "season"]]
    availability = pd.DataFrame({
        "Variável": data_cols,
        "Disponibilidade (%)": [valid_percent(filtered[c]) for c in data_cols],
        "Ausentes": [int(filtered[c].isna().sum()) for c in data_cols],
    }).sort_values(["Disponibilidade (%)", "Variável"], ascending=[True, True])

    fig = px.bar(
        availability.head(25),
        x="Disponibilidade (%)",
        y="Variável",
        orientation="h",
        title="25 variáveis com menor disponibilidade de dados",
        hover_data=["Ausentes"],
    )
    fig.update_layout(height=650, yaxis={"categoryorder": "total ascending"})
    st.plotly_chart(fig, use_container_width=True)

    with st.expander("Tabela completa de disponibilidade"):
        st.dataframe(availability, use_container_width=True)

    with st.expander("Pré-visualização dos dados"):
        st.dataframe(
            filtered.drop(columns=["_obs"]).head(200),
            use_container_width=True
        )

elif page == "Meteorologia":
    st.header("Meteorologia")

    defaults = existing(filtered, MET_MAIN)
    options = existing(filtered, MET_MAIN + MET_AUX)

    st.info(
        "As unidades não estão registradas nos cabeçalhos do XLSX. "
        "Por isso, esta versão exibe os nomes originais das variáveis sem atribuir unidades não verificadas."
    )

    selected = st.multiselect(
        "Variáveis meteorológicas",
        options=options,
        default=defaults,
    )

    make_line_chart(
        filtered,
        selected,
        "Variáveis meteorológicas — ordem sequencial das observações"
    )
    stats_table(filtered, selected)

    st.subheader("Cobertura dos produtos meteorológicos")
    cov = pd.DataFrame({
        "Variável": options,
        "Disponibilidade (%)": [valid_percent(filtered[c]) for c in options],
        "Ausentes": [filtered[c].isna().sum() for c in options],
    })
    st.dataframe(cov, use_container_width=True)

elif page == "Fluxos de Carbono":
    st.header("Fluxos de Carbono")

    defaults = existing(filtered, CARBON_MAIN)
    options = existing(filtered, CARBON_MAIN + CARBON_AUX)

    st.info(
        "A figura compara os produtos disponíveis no arquivo. "
        "As unidades devem ser confirmadas a partir da documentação do processamento antes de serem publicadas no eixo."
    )

    selected = st.multiselect(
        "Variáveis de carbono",
        options=options,
        default=defaults,
    )

    make_line_chart(
        filtered,
        selected,
        "NEE, Reco, GPP e produtos relacionados"
    )
    stats_table(filtered, selected)

    if len(selected) >= 2:
        st.subheader("Relação entre duas variáveis")
        c1, c2 = st.columns(2)
        xvar = c1.selectbox("Eixo X", selected, index=0)
        yvar = c2.selectbox("Eixo Y", selected, index=1)
        dxy = filtered[[xvar, yvar]].dropna()

        fig = px.scatter(
            dxy,
            x=xvar,
            y=yvar,
            opacity=0.5,
            title=f"{yvar} × {xvar}",
        )
        st.plotly_chart(fig, use_container_width=True)

        if len(dxy) >= 3:
            r = dxy[xvar].corr(dxy[yvar])
            st.metric("Correlação de Pearson (r)", f"{r:.3f}")

elif page == "Qualidade e Gap-filling":
    st.header("Qualidade e Gap-filling")

    qc_options = existing(filtered, QC_COLUMNS)
    gap_options = existing(filtered, GAPFILL_DIAGNOSTICS)

    st.markdown(
        """
        Esta seção mantém os **códigos originais** de QC e gap-filling.
        A interpretação semântica dos valores (por exemplo, o significado exato de 0, 1, 2 ou 3)
        deve seguir a documentação do algoritmo/processamento utilizado.
        """
    )

    if qc_options:
        st.subheader("Flags de qualidade")
        chosen_qc = st.selectbox("Variável QC", qc_options)

        q = (
            filtered[chosen_qc]
            .astype("string")
            .fillna("NA")
            .value_counts(dropna=False)
            .rename_axis("Código")
            .reset_index(name="Frequência")
        )
        q["Percentual (%)"] = 100 * q["Frequência"] / q["Frequência"].sum()

        fig = px.bar(
            q,
            x="Código",
            y="Frequência",
            text="Percentual (%)",
            title=f"Distribuição dos códigos — {chosen_qc}",
        )
        fig.update_traces(texttemplate="%{text:.1f}%")
        st.plotly_chart(fig, use_container_width=True)
        st.dataframe(q, use_container_width=True)

    if gap_options:
        st.subheader("Diagnósticos de gap-filling")
        selected_gap = st.multiselect(
            "Variáveis diagnósticas",
            options=gap_options,
            default=gap_options[:4],
        )
        stats_table(filtered, selected_gap)

elif page == "Particionamento de Carbono":
    st.header("Particionamento de Carbono")

    partition_cols = existing(
        filtered,
        [
            "Reco_DT", "GPP_DT", "Reco_DT_SD", "GPP_DT_SD",
            "FP_Temp_NEW", "E_0_NEW", "FP_VARnight", "FP_VARday",
            "NEW_FP_Temp", "NEW_FP_VPD", "FP_RRef_Night",
            "FP_qc", "FP_dRecPar", "FP_errorcode", "FP_GPP2000",
            "FP_k", "FP_beta", "FP_alpha", "FP_RRef", "FP_E0",
            "FP_k_sd", "FP_beta_sd", "FP_alpha_sd", "FP_RRef_sd", "FP_E0_sd"
        ],
    )

    selected = st.multiselect(
        "Produtos/parâmetros",
        options=partition_cols,
        default=existing(filtered, ["Reco_DT", "GPP_DT", "Reco_DT_SD", "GPP_DT_SD"]),
    )

    make_line_chart(
        filtered,
        selected,
        "Produtos e parâmetros de particionamento"
    )
    stats_table(filtered, selected)

elif page == "Sobre os Dados":
    st.header("Sobre os Dados")

    st.markdown(
        """
        ### Estrutura detectada

        O XLSX possui **63 colunas originais** e foi organizado em grupos que incluem:
        NEE, radiação global (`Rg`), temperatura do ar (`Tair`), VPD,
        indicadores de preenchimento de falhas e produtos de particionamento
        como `Reco_DT` e `GPP_DT`.

        A coluna `season` foi preservada como identificador de período. Ela **não é tratada
        como timestamp**, pois o arquivo não contém uma coluna explícita de data-hora.
        Essa decisão evita atribuir datas artificiais aos registros.

        ### Unidades e metadados

        Os cabeçalhos do arquivo não contêm unidades. Antes da publicação definitiva,
        recomenda-se adicionar uma tabela de metadados com **nome da variável, definição,
        unidade, método de processamento e significado dos códigos QC**.
        """
    )

    schema = pd.DataFrame({
        "Variável": [c for c in df.columns if c != "_obs"],
        "Tipo no aplicativo": [str(df[c].dtype) for c in df.columns if c != "_obs"],
        "Ausentes": [int(df[c].isna().sum()) for c in df.columns if c != "_obs"],
        "Disponibilidade (%)": [
            valid_percent(df[c]) for c in df.columns if c != "_obs"
        ],
    })
    st.dataframe(schema, use_container_width=True)

elif page == "Solicitar Dados":
    st.header("Solicitar Dados")

    st.warning(
        "Os dados são disponibilizados nesta plataforma somente para visualização. "
        "Não há download público direto."
    )

    with st.form("request_form"):
        name = st.text_input("Nome")
        institution = st.text_input("Instituição")
        email = st.text_input("E-mail")
        purpose = st.text_area("Finalidade científica/acadêmica da solicitação")
        dataset = st.text_input("Dados ou variáveis de interesse")
        submitted = st.form_submit_button("Gerar solicitação")

        if submitted:
            if not name or not email or not purpose:
                st.error("Preencha pelo menos nome, e-mail e finalidade.")
            else:
                st.success(
                    "Solicitação preparada. Nesta versão, o formulário ainda não envia "
                    "nem armazena dados automaticamente."
                )
                st.text_area(
                    "Resumo da solicitação",
                    value=(
                        f"Nome: {name}\n"
                        f"Instituição: {institution}\n"
                        f"E-mail: {email}\n"
                        f"Dados/variáveis: {dataset}\n\n"
                        f"Finalidade:\n{purpose}"
                    ),
                    height=220,
                )

st.divider()
st.caption(
    "EcoFlux Brasil • Plataforma científica de visualização • "
    "Sem download público direto dos dados"
)
