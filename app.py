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
    .block-container {padding-top: 1.3rem; padding-bottom: 2rem;}
    h1, h2, h3 {letter-spacing: -0.02em;}
    [data-testid="stMetricValue"] {font-size: 1.45rem;}
    </style>
    """,
    unsafe_allow_html=True,
)

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

def season_label(value):
    try:
        s = str(int(float(value))).zfill(7)
        year = int(s[:4])
        month = int(s[-3:])
        months = ["Jan", "Fev", "Mar", "Abr", "Mai", "Jun", "Jul", "Ago", "Set", "Out", "Nov", "Dez"]
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

    df["season_label"] = df["season"].apply(season_label)
    df["_global_obs"] = np.arange(1, len(df) + 1)
    df["_season_obs"] = df.groupby("season", sort=False).cumcount()
    df["elapsed_hours"] = df["_season_obs"] * (SAMPLING_MINUTES / 60.0)
    df["elapsed_days"] = df["elapsed_hours"] / 24.0

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

def valid_pct(s):
    return 100 * s.notna().mean() if len(s) else np.nan

def summary_table(df, var):
    s = pd.to_numeric(df[var], errors="coerce")
    return pd.DataFrame({
        "Métrica": ["N válido", "Disponibilidade (%)", "Média", "Mediana", "Desvio-padrão", "Mínimo", "Máximo"],
        "Valor": [
            int(s.notna().sum()),
            round(valid_pct(s), 2),
            s.mean(),
            s.median(),
            s.std(),
            s.min(),
            s.max(),
        ]
    })

def aggregate_relative(part, var, resolution):
    d = part[["_season_obs", "elapsed_hours", "elapsed_days", var]].copy()

    if resolution == "30 min":
        d["x"] = d["elapsed_days"]
        return d[["x", var]]

    factor = {
        "Diário": 48,
        "Semanal": 48 * 7,
        "Mensal aproximado": 48 * 30,
    }[resolution]

    d["bin"] = d["_season_obs"] // factor
    out = d.groupby("bin", as_index=False)[var].mean()
    out["x"] = out["bin"] * factor / 48.0
    return out[["x", var]]

def plot_variable_by_season(df, var, title, resolution):
    fig = go.Figure()

    for season_name in pd.unique(df["season_label"]):
        part = df[df["season_label"] == season_name].copy()
        agg = aggregate_relative(part, var, resolution)

        fig.add_trace(
            go.Scattergl(
                x=agg["x"],
                y=agg[var],
                mode="lines",
                name=season_name,
                connectgaps=False,
            )
        )

    fig.update_layout(
        title=title,
        xaxis_title="Tempo relativo dentro do bloco (dias)",
        yaxis_title=var,
        hovermode="x unified",
        height=420,
        margin=dict(l=20, r=20, t=55, b=20),
        legend_title="season",
    )
    st.plotly_chart(fig, use_container_width=True)

def plot_scatter(df, xvar, yvar, title):
    d = df[[xvar, yvar, "season_label"]].dropna()
    if d.empty:
        st.info("Não há pares válidos para este gráfico.")
        return
    fig = px.scatter(
        d,
        x=xvar,
        y=yvar,
        color="season_label",
        opacity=0.5,
        title=title,
    )
    st.plotly_chart(fig, use_container_width=True)

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

st.sidebar.caption(
    "Política de acesso: visualização pública permitida; dados brutos somente mediante autorização."
)

if uploaded is None:
    st.info("Carregue o XLSX para visualizar os dados.")
    st.warning("Não coloque o XLSX bruto em um repositório público do GitHub.")
    st.stop()

try:
    df, sheet_name = load_xlsx(uploaded)
except Exception as e:
    st.error(f"Não foi possível ler o XLSX: {e}")
    st.stop()

season_options = list(pd.unique(df["season_label"]))
selected_seasons = st.sidebar.multiselect(
    "Período (season)",
    options=season_options,
    default=season_options,
)

filtered = df[df["season_label"].isin(selected_seasons)].copy()

resolution = st.sidebar.selectbox(
    "Agregação temporal",
    ["30 min", "Diário", "Semanal", "Mensal aproximado"],
    index=1,
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
    c2.metric("Variáveis originais", 63)
    c3.metric("Resolução original", "30 min")
    c4.metric("Compatibilidade", f"{compatibility:.0f}%")

    st.caption(f"Aba lida: {sheet_name}")

    st.warning(
        "As datas absolutas não são reconstruídas para blocos sem timestamp documentado. "
        "Os gráficos usam tempo relativo dentro de cada `season`."
    )

    block_summary = (
        df.groupby(["season", "season_label"], sort=False)
        .agg(Registros=("_season_obs", "size"))
        .reset_index()
    )
    block_summary["Duração equivalente (dias)"] = block_summary["Registros"] / 48.0

    st.subheader("Blocos observacionais")
    st.dataframe(block_summary, use_container_width=True)

    data_cols = [
        c for c in df.columns
        if c not in ["season", "season_label", "_global_obs", "_season_obs", "elapsed_hours", "elapsed_days", "known_datetime"]
    ]

    availability = pd.DataFrame({
        "Variável": data_cols,
        "Disponibilidade (%)": [valid_pct(filtered[c]) for c in data_cols],
        "Ausentes": [int(filtered[c].isna().sum()) for c in data_cols],
    }).sort_values(["Disponibilidade (%)", "Variável"])

    st.subheader("Disponibilidade das variáveis")
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

    with st.expander("Tabela completa"):
        st.dataframe(availability, use_container_width=True)

# ============================================================
# METEOROLOGIA
# ============================================================

elif page == "Meteorologia":
    st.header("Meteorologia")

    st.info(
        "Cada variável é mostrada em gráfico próprio para evitar distorções causadas por escalas diferentes."
    )

    met_groups = [
        ("Radiação", existing(filtered, ["Rg_fall", "Rg_f", "Rg_orig", "PotRad_NEW"])),
        ("Temperatura do ar", existing(filtered, ["Tair_fall", "Tair_f", "Tair_orig", "FP_Temp_NEW", "NEW_FP_Temp"])),
        ("VPD", existing(filtered, ["VPD_fall", "VPD_f", "VPD_orig", "NEW_FP_VPD"])),
    ]

    for group_name, vars_available in met_groups:
        if not vars_available:
            continue

        st.subheader(group_name)

        var = st.selectbox(
            f"Variável — {group_name}",
            options=vars_available,
            index=0,
            key=f"met_{group_name}",
        )

        plot_variable_by_season(
            filtered,
            var,
            f"{group_name}: {var}",
            resolution,
        )

        with st.expander(f"Estatísticas — {var}"):
            st.dataframe(summary_table(filtered, var), use_container_width=True)

    st.caption(
        "As unidades físicas não são apresentadas até que o dicionário de metadados seja confirmado."
    )

# ============================================================
# FLUXOS DE CARBONO
# ============================================================

elif page == "Fluxos de Carbono":
    st.header("Fluxos de Carbono")

    st.info(
        "NEE, Reco e GPP são apresentados separadamente para preservar suas escalas e facilitar a comparação entre `season`."
    )

    carbon_groups = [
        ("NEE", existing(filtered, ["NEE_fall", "NEE_f", "NEE_orig", "NEE_fsd"])),
        ("Reco", existing(filtered, ["Reco_DT", "Reco_DT_SD", "FP_RRef", "FP_RRef_Night"])),
        ("GPP", existing(filtered, ["GPP_DT", "GPP_DT_SD", "FP_GPP2000"])),
    ]

    selected_main = {}

    for group_name, vars_available in carbon_groups:
        if not vars_available:
            continue

        st.subheader(group_name)

        var = st.selectbox(
            f"Variável — {group_name}",
            options=vars_available,
            index=0,
            key=f"carbon_{group_name}",
        )
        selected_main[group_name] = var

        plot_variable_by_season(
            filtered,
            var,
            f"{group_name}: {var}",
            resolution,
        )

        with st.expander(f"Estatísticas — {var}"):
            st.dataframe(summary_table(filtered, var), use_container_width=True)

    if "NEE" in selected_main and "GPP" in selected_main:
        st.subheader("Relações entre fluxos")
        plot_scatter(
            filtered,
            selected_main["NEE"],
            selected_main["GPP"],
            f"{selected_main['GPP']} × {selected_main['NEE']}",
        )

# ============================================================
# QUALIDADE
# ============================================================

elif page == "Qualidade e Gap-filling":
    st.header("Qualidade e Gap-filling")

    qc_vars = existing(
        filtered,
        [
            "NEE_fqc", "NEE_fall_qc",
            "Rg_fqc", "Rg_fall_qc",
            "Tair_fqc", "Tair_fall_qc",
            "VPD_fqc", "VPD_fall_qc",
            "FP_qc", "FP_errorcode"
        ],
    )

    gap_vars = existing(
        filtered,
        [
            "NEE_fnum", "NEE_fmeth", "NEE_fwin", "NEE_fsd",
            "Rg_fnum", "Rg_fmeth", "Rg_fwin", "Rg_fsd",
            "Tair_fnum", "Tair_fmeth", "Tair_fwin", "Tair_fsd",
            "VPD_fnum", "VPD_fmeth", "VPD_fwin", "VPD_fsd"
        ],
    )

    if qc_vars:
        chosen = st.selectbox("Flag / código QC", qc_vars)
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

    if gap_vars:
        st.subheader("Diagnósticos de gap-filling")
        chosen_gap = st.multiselect(
            "Variáveis diagnósticas",
            options=gap_vars,
            default=gap_vars[:4],
        )
        if chosen_gap:
            desc = filtered[chosen_gap].describe().T
            st.dataframe(desc, use_container_width=True)

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
            "FP_k_sd", "FP_beta_sd", "FP_alpha_sd", "FP_RRef_sd", "FP_E0_sd"
        ],
    )

    if options:
        var = st.selectbox("Produto / parâmetro", options)
        plot_variable_by_season(
            filtered,
            var,
            f"Particionamento: {var}",
            resolution,
        )
        st.dataframe(summary_table(filtered, var), use_container_width=True)

# ============================================================
# SOBRE
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
        A resolução original é de **30 minutos** e os registros seguem continuamente
        dentro de cada bloco `season`. A coluna `season` codifica **ano e mês**.

        Como o arquivo não contém timestamp absoluto para todos os blocos,
        os gráficos usam **tempo relativo dentro de cada bloco**.

        ### Transparência científica
        O aplicativo não atribui unidades físicas ou significados de QC sem
        documentação confirmada.
        """
    )

# ============================================================
# SOLICITAÇÃO
# ============================================================

elif page == "Solicitar Dados":
    st.header("Solicitar Dados")

    st.warning(
        "Não há download público direto. O fornecimento dos dados depende de autorização expressa do responsável."
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
                st.error("Preencha nome, e-mail e finalidade e confirme a declaração.")
            else:
                st.success(
                    "Solicitação preparada. Nesta versão gratuita, o formulário ainda não envia nem armazena automaticamente."
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
    "EcoFlux Brasil • Visualização científica pública • Dados brutos somente mediante autorização"
)
