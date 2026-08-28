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
        .block-container {padding-top: 1.6rem; padding-bottom: 2rem;}
        h1, h2, h3 {letter-spacing: -0.02em;}
        [data-testid="stMetricValue"] {font-size: 1.6rem;}
    </style>
    """,
    unsafe_allow_html=True,
)

@st.cache_data(show_spinner=False)
def load_xlsx(uploaded_file):
    xls = pd.ExcelFile(uploaded_file)
    sheet = xls.sheet_names[0]
    df = pd.read_excel(uploaded_file, sheet_name=sheet)
    return df, sheet

def find_datetime_column(df):
    candidates = [
        "TIMESTAMP", "Timestamp", "timestamp", "DateTime", "Datetime",
        "datetime", "DATA_HORA", "DataHora", "date_time", "DATE"
    ]
    for c in candidates:
        if c in df.columns:
            s = pd.to_datetime(df[c], errors="coerce")
            if s.notna().mean() > 0.7:
                return c, s
    for c in df.columns:
        name = str(c).lower()
        if any(k in name for k in ["time", "date", "data", "hora"]):
            s = pd.to_datetime(df[c], errors="coerce")
            if s.notna().mean() > 0.7:
                return c, s
    return None, None

def numeric_columns(df):
    return [c for c in df.columns if pd.api.types.is_numeric_dtype(df[c])]

def available(df, names):
    lower = {str(c).lower(): c for c in df.columns}
    out = []
    for n in names:
        if n.lower() in lower:
            out.append(lower[n.lower()])
    return out

def guess_group(df, keys):
    cols = []
    for c in df.columns:
        lc = str(c).lower()
        if any(k.lower() in lc for k in keys):
            if pd.api.types.is_numeric_dtype(df[c]):
                cols.append(c)
    return cols

def render_timeseries(data, dt_col, variables, title):
    if not variables:
        st.info("Nenhuma variável compatível foi identificada automaticamente nesta categoria.")
        return
    fig = go.Figure()
    for var in variables:
        fig.add_trace(
            go.Scattergl(
                x=data[dt_col],
                y=data[var],
                mode="lines",
                name=str(var),
            )
        )
    fig.update_layout(
        title=title,
        xaxis_title="Data / hora",
        yaxis_title="Valor",
        legend_title="Variável",
        hovermode="x unified",
        height=500,
        margin=dict(l=20, r=20, t=55, b=20),
    )
    st.plotly_chart(fig, use_container_width=True)

def stats_table(data, variables):
    if not variables:
        return
    desc = data[variables].describe().T
    wanted = [c for c in ["count", "mean", "std", "min", "25%", "50%", "75%", "max"] if c in desc.columns]
    st.dataframe(desc[wanted], use_container_width=True)

st.title("🌱 EcoFlux Brasil")
st.caption("Plataforma de Dados Micrometeorológicos e Fluxos Ecossistêmicos")

st.sidebar.header("Navegação")
page = st.sidebar.radio(
    "Seção",
    [
        "Visão Geral",
        "Meteorologia",
        "Fluxos de Carbono",
        "Balanço de Energia",
        "Qualidade dos Dados",
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
        "Este carregamento serve para desenvolvimento e validação. "
        "O arquivo não é disponibilizado para download pelo aplicativo."
    ),
)

if uploaded is None:
    st.info(
        "A plataforma está funcionando. Para validar os gráficos com dados reais, "
        "carregue um arquivo XLSX na barra lateral. Em uma etapa posterior, "
        "os dados poderão ser conectados a uma fonte protegida para visualização pública."
    )

    st.markdown(
        """
        ### Estrutura da plataforma

        **Visão Geral** — resumo do conjunto de dados, período observado e indicadores básicos.

        **Meteorologia** — séries temporais de temperatura do ar, umidade, VPD, radiação,
        precipitação, vento e outras variáveis meteorológicas disponíveis.

        **Fluxos de Carbono** — visualização de NEE, GPP, Reco e variáveis correlatas.

        **Balanço de Energia** — análise de Rn, H, LE, G e variáveis associadas.

        **Qualidade dos Dados** — inspeção de flags de controle de qualidade,
        preenchimento de falhas e cobertura temporal.

        **Solicitar Dados** — orientação para solicitação de acesso aos dados.
        """
    )
    st.stop()

try:
    df, sheet_name = load_xlsx(uploaded)
except Exception as e:
    st.error(f"Não foi possível ler o arquivo XLSX: {e}")
    st.stop()

dt_name, dt_series = find_datetime_column(df)

if dt_name is not None:
    df = df.copy()
    df["_datetime"] = dt_series
    df = df[df["_datetime"].notna()].sort_values("_datetime")
    dt_col = "_datetime"
else:
    dt_col = None

num_cols = numeric_columns(df)

if dt_col is not None and not df.empty:
    min_date = df[dt_col].min().date()
    max_date = df[dt_col].max().date()
    st.sidebar.subheader("Período")
    date_range = st.sidebar.date_input(
        "Intervalo",
        value=(min_date, max_date),
        min_value=min_date,
        max_value=max_date,
    )
    filtered = df.copy()
    if isinstance(date_range, tuple) and len(date_range) == 2:
        start, end = date_range
        filtered = filtered[
            (filtered[dt_col].dt.date >= start)
            & (filtered[dt_col].dt.date <= end)
        ]
else:
    filtered = df

carbon_cols = available(df, ["NEE", "GPP", "Reco", "Reco_DT", "GPP_DT"])
if not carbon_cols:
    carbon_cols = guess_group(df, ["nee", "gpp", "reco", "co2", "carbon"])

met_cols = available(df, ["Tair", "VPD", "Rg", "RH", "WS", "USTAR", "P", "PA"])
if not met_cols:
    met_cols = guess_group(
        df,
        ["tair", "temp", "vpd", "rh", "humidity", "rg", "rad", "prec", "rain", "wind", "ws", "ustar"]
    )

energy_cols = available(df, ["Rn", "H", "LE", "G"])
if not energy_cols:
    energy_cols = guess_group(df, ["rn", "netrad", "latent", "sensible", "soilheat"])

qc_cols = guess_group(df, ["qc", "quality", "flag", "gap", "fill"])

if page == "Visão Geral":
    st.header("Visão Geral")

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Registros", f"{len(filtered):,}".replace(",", "."))
    c2.metric("Variáveis", len(df.columns))

    if dt_col is not None and not filtered.empty:
        c3.metric("Início", filtered[dt_col].min().strftime("%d/%m/%Y"))
        c4.metric("Fim", filtered[dt_col].max().strftime("%d/%m/%Y"))
    else:
        c3.metric("Início", "—")
        c4.metric("Fim", "—")

    st.caption(f"Aba lida: {sheet_name}")

    st.subheader("Cobertura das variáveis")
    missing = pd.DataFrame({
        "Variável": df.columns.astype(str),
        "Disponibilidade (%)": (1 - df.isna().mean()).values * 100,
        "Ausentes": df.isna().sum().values,
    }).sort_values("Disponibilidade (%)")

    fig = px.bar(
        missing.tail(20),
        x="Disponibilidade (%)",
        y="Variável",
        orientation="h",
        title="20 variáveis com maior disponibilidade",
    )
    fig.update_layout(height=550)
    st.plotly_chart(fig, use_container_width=True)

    with st.expander("Pré-visualização da tabela"):
        st.dataframe(filtered.head(200), use_container_width=True)

elif page == "Meteorologia":
    st.header("Meteorologia")
    if dt_col is None:
        st.warning("Não foi possível identificar automaticamente uma coluna de data/hora.")
    else:
        selected = st.multiselect(
            "Variáveis meteorológicas",
            options=num_cols,
            default=met_cols[:4],
        )
        render_timeseries(filtered, dt_col, selected, "Séries temporais meteorológicas")
        stats_table(filtered, selected)

elif page == "Fluxos de Carbono":
    st.header("Fluxos de Carbono")
    if dt_col is None:
        st.warning("Não foi possível identificar automaticamente uma coluna de data/hora.")
    else:
        selected = st.multiselect(
            "Variáveis de carbono",
            options=num_cols,
            default=carbon_cols[:4],
        )
        render_timeseries(filtered, dt_col, selected, "NEE, GPP, Reco e variáveis relacionadas")
        stats_table(filtered, selected)

        if len(selected) >= 2:
            st.subheader("Relação entre variáveis")
            x_var = st.selectbox("Eixo X", selected, index=0)
            y_var = st.selectbox("Eixo Y", selected, index=1)
            fig = px.scatter(
                filtered,
                x=x_var,
                y=y_var,
                opacity=0.55,
                title=f"{y_var} × {x_var}",
            )
            st.plotly_chart(fig, use_container_width=True)

elif page == "Balanço de Energia":
    st.header("Balanço de Energia")
    if dt_col is None:
        st.warning("Não foi possível identificar automaticamente uma coluna de data/hora.")
    else:
        selected = st.multiselect(
            "Variáveis do balanço de energia",
            options=num_cols,
            default=energy_cols[:4],
        )
        render_timeseries(filtered, dt_col, selected, "Componentes do balanço de energia")
        stats_table(filtered, selected)

elif page == "Qualidade dos Dados":
    st.header("Qualidade dos Dados")

    st.write(
        "Esta seção identifica automaticamente colunas cujos nomes sugerem "
        "controle de qualidade, flags, gap-filling ou preenchimento de falhas."
    )

    if qc_cols:
        qc_summary = pd.DataFrame({
            "Variável": qc_cols,
            "Valores válidos": [filtered[c].notna().sum() for c in qc_cols],
            "Ausentes": [filtered[c].isna().sum() for c in qc_cols],
            "Disponibilidade (%)": [
                100 * filtered[c].notna().mean() if len(filtered) else np.nan
                for c in qc_cols
            ],
        })
        st.dataframe(qc_summary, use_container_width=True)

        chosen = st.selectbox("Inspecionar variável de qualidade", qc_cols)
        value_counts = (
            filtered[chosen]
            .astype("string")
            .fillna("NA")
            .value_counts()
            .head(30)
            .rename_axis("Classe")
            .reset_index(name="Frequência")
        )
        fig = px.bar(
            value_counts,
            x="Classe",
            y="Frequência",
            title=f"Distribuição de {chosen}",
        )
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info(
            "Nenhuma coluna de QC/gap-filling foi reconhecida automaticamente. "
            "Podemos mapear explicitamente os nomes das variáveis do seu arquivo."
        )

elif page == "Sobre os Dados":
    st.header("Sobre os Dados")

    st.markdown(
        """
        Esta plataforma foi concebida para visualização científica de dados
        micrometeorológicos e de **Eddy Covariance**, incluindo variáveis meteorológicas,
        fluxos de carbono, componentes do balanço de energia e indicadores de qualidade.

        A interpretação de produtos como **NEE, GPP e Reco** deve considerar
        os procedimentos de controle de qualidade, correções, filtragem por turbulência
        e métodos de preenchimento de falhas adotados no processamento original.
        """
    )

    st.subheader("Estrutura detectada no arquivo")
    schema = pd.DataFrame({
        "Variável": df.columns.astype(str),
        "Tipo": [str(df[c].dtype) for c in df.columns],
        "Ausentes": [int(df[c].isna().sum()) for c in df.columns],
    })
    st.dataframe(schema, use_container_width=True)

elif page == "Solicitar Dados":
    st.header("Solicitar Dados")

    st.warning(
        "Os dados exibidos nesta plataforma destinam-se à visualização. "
        "O download não é disponibilizado publicamente."
    )

    st.write(
        "Solicitações de acesso aos dados devem ser avaliadas pelo responsável "
        "pela plataforma. A versão pública futura poderá incluir um fluxo formal "
        "de solicitação, justificativa de uso, análise e autorização."
    )

    with st.form("request_form"):
        name = st.text_input("Nome")
        institution = st.text_input("Instituição")
        email = st.text_input("E-mail")
        purpose = st.text_area("Finalidade científica ou acadêmica da solicitação")
        submitted = st.form_submit_button("Gerar resumo da solicitação")

        if submitted:
            if not name or not email or not purpose:
                st.error("Preencha nome, e-mail e finalidade.")
            else:
                st.success(
                    "Resumo gerado. Nesta versão inicial, a solicitação ainda não é "
                    "armazenada nem enviada automaticamente."
                )
                st.text_area(
                    "Resumo",
                    value=(
                        f"Nome: {name}\n"
                        f"Instituição: {institution}\n"
                        f"E-mail: {email}\n\n"
                        f"Finalidade:\n{purpose}"
                    ),
                    height=180,
                )

st.divider()
st.caption(
    "EcoFlux Brasil • Plataforma científica de visualização • "
    "Sem download público direto dos dados"
)
