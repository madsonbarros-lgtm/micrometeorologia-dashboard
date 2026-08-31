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

def stats_df(df, var):
    s = pd.to_numeric(df[var], errors="coerce")
    return pd.DataFrame({
        "Métrica": [
            "N válido", "Disponibilidade (%)", "Média", "Mediana",
            "Desvio-padrão", "Mínimo", "Máximo"
        ],
        "Valor": [
            int(s.notna().sum()),
            round(valid_pct(s), 2),
            s.mean(),
            s.median(),
            s.std(),
            s.min(),
            s.max(),
        ],
    })

def aggregate_relative(part, var, resolution):
    d = part[["_season_obs", "elapsed_days", var]].copy()

    if resolution == "30 min":
        d["x"] = d["elapsed_days"]
        return d[["x", var]]

    factor = {"Diário": 48, "Semanal": 48 * 7}[resolution]
    d["bin"] = d["_season_obs"] // factor
    out = d.groupby("bin", as_index=False)[var].mean()
    out["x"] = out["bin"] * factor / 48.0
    return out[["x", var]]

def clip_for_display(series, enabled=True, low_q=0.005, high_q=0.995):
    s = pd.to_numeric(series, errors="coerce")
    if not enabled or s.dropna().empty:
        return s
    lo = s.quantile(low_q)
    hi = s.quantile(high_q)
    return s.clip(lo, hi)

def plot_by_season(df, var, title, resolution, clip_extremes=False):
    fig = go.Figure()

    for season_name in pd.unique(df["season_label"]):
        part = df[df["season_label"] == season_name].copy()

        if clip_extremes and resolution == "30 min":
            part[var] = clip_for_display(part[var], enabled=True)

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

def show_stat_cards(df, var):
    s = pd.to_numeric(df[var], errors="coerce")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Média", f"{s.mean():.3f}" if s.notna().any() else "—")
    c2.metric("Mediana", f"{s.median():.3f}" if s.notna().any() else "—")
    c3.metric("Desvio-padrão", f"{s.std():.3f}" if s.notna().any() else "—")
    c4.metric("Disponibilidade", f"{valid_pct(s):.1f}%")

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
    help="O arquivo é usado apenas na sessão e não é oferecido para download.",
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
    ["30 min", "Diário", "Semanal"],
    index=1,
)

clip_sd = st.sidebar.checkbox(
    "Limitar extremos apenas na exibição de incertezas (_SD)",
    value=True,
    help=(
        "Aplica winsorização visual entre os percentis 0,5% e 99,5% apenas no gráfico. "
        "Os dados originais e as estatísticas permanecem inalterados."
    ),
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

# ============================================================
# METEOROLOGIA
# ============================================================

elif page == "Meteorologia":
    st.header("Meteorologia")

    st.info(
        "Radiação, temperatura do ar e VPD aparecem em gráficos separados para preservar suas escalas."
    )

    groups = [
        ("Radiação", existing(filtered, ["Rg_fall", "Rg_f", "Rg_orig", "PotRad_NEW"])),
        ("Temperatura do ar", existing(filtered, ["Tair_fall", "Tair_f", "Tair_orig", "FP_Temp_NEW", "NEW_FP_Temp"])),
        ("VPD", existing(filtered, ["VPD_fall", "VPD_f", "VPD_orig", "NEW_FP_VPD"])),
    ]

    for title, opts in groups:
        if not opts:
            continue
        st.subheader(title)
        var = st.selectbox(f"Variável — {title}", opts, key=f"met_{title}")
        plot_by_season(filtered, var, f"{title}: {var}", resolution)
        show_stat_cards(filtered, var)

# ============================================================
# FLUXOS DE CARBONO
# ============================================================

elif page == "Fluxos de Carbono":
    st.header("Fluxos de Carbono")

    st.info(
        "NEE, Reco e GPP são exibidos separadamente. Cada gráfico compara os `season` selecionados."
    )

    groups = [
        ("NEE", existing(filtered, ["NEE_fall", "NEE_f", "NEE_orig"])),
        ("Reco", existing(filtered, ["Reco_DT", "FP_RRef", "FP_RRef_Night"])),
        ("GPP", existing(filtered, ["GPP_DT", "FP_GPP2000"])),
    ]

    selected_main = {}

    for title, opts in groups:
        if not opts:
            continue

        st.subheader(title)
        var = st.selectbox(f"Variável — {title}", opts, key=f"carbon_{title}")
        selected_main[title] = var

        plot_by_season(filtered, var, f"{title}: {var}", resolution)
        show_stat_cards(filtered, var)

        with st.expander(f"Estatísticas completas — {var}"):
            st.dataframe(stats_df(filtered, var), use_container_width=True)

    if "NEE" in selected_main and "GPP" in selected_main:
        st.subheader("Relação NEE × GPP")
        d = filtered[[selected_main["NEE"], selected_main["GPP"], "season_label"]].dropna()
        if not d.empty:
            fig = px.scatter(
                d,
                x=selected_main["NEE"],
                y=selected_main["GPP"],
                color="season_label",
                opacity=0.45,
                title=f"{selected_main['GPP']} × {selected_main['NEE']}",
            )
            st.plotly_chart(fig, use_container_width=True)

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

# ============================================================
# PARTICIONAMENTO
# ============================================================

elif page == "Particionamento de Carbono":
    st.header("Particionamento de Carbono")

    st.info(
        "Produtos e incertezas são separados para evitar que valores extremos das colunas `_SD` comprimam os demais sinais."
    )

    st.subheader("Produtos principais")

    product_groups = [
        ("Reco", existing(filtered, ["Reco_DT"])),
        ("GPP", existing(filtered, ["GPP_DT"])),
    ]

    for title, opts in product_groups:
        if not opts:
            continue
        var = opts[0]
        plot_by_season(filtered, var, f"{title}: {var}", resolution)
        show_stat_cards(filtered, var)

    st.subheader("Incertezas / desvio-padrão")

    sd_groups = [
        ("Reco", existing(filtered, ["Reco_DT_SD"])),
        ("GPP", existing(filtered, ["GPP_DT_SD"])),
    ]

    for title, opts in sd_groups:
        if not opts:
            continue
        var = opts[0]
        plot_by_season(
            filtered,
            var,
            f"Incerteza {title}: {var}",
            resolution,
            clip_extremes=clip_sd,
        )
        show_stat_cards(filtered, var)

        if clip_sd:
            st.caption(
                f"No gráfico de {var}, os extremos são limitados apenas visualmente "
                f"entre os percentis 0,5% e 99,5%. Os dados e estatísticas permanecem inalterados."
            )

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
        O aplicativo não altera os dados originais. Quando a limitação visual de extremos
        é ativada para variáveis `_SD`, ela é aplicada apenas ao gráfico.
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
