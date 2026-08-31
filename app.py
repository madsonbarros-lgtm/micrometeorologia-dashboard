import io
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import streamlit as st

st.set_page_config(
    page_title="EcoFlux Brasil",
    page_icon="🌿",
    layout="wide",
)

# ============================================================
# EcoFlux Brasil — V22
# Estrutura orientada à planilha original de processamento
# ============================================================

MISSING_SENTINELS = {-9999, -9999.0}

TEMPORAL_FIELDS = {
    "date time", "datetime", "date_time", "datatime", "timestamp",
    "year", "doy", "day_of_year", "hour", "minute", "second",
    "date", "time", "season",
}

QC_TOKENS = ("_fqc", "_fall_qc", "qc_", "_qc")
AUXILIARY_SUFFIXES = ("_fnum", "_fmeth", "_fwin")
UNCERTAINTY_SUFFIXES = ("_fsd", "_fsdu", "_fsdug", "_sd")

GAPFILL_FAMILIES = ["NEE", "LE", "H", "Rg", "VPD", "rH", "Tair", "Tsoil"]


# Organização científica típica de uma torre micrometeorológica.
# As unidades exibidas nas séries continuam vindo da planilha original;
# estas categorias servem para navegação e documentação, não para sobrescrever metadados.
SCIENTIFIC_STRUCTURE = {
    "Temporal e Identificação": {
        "aliases": ["TIMESTAMP", "Date", "Time", "RECORD"],
        "description": "Referência temporal e identificação sequencial dos registros.",
    },
    "Ventos e Turbulência": {
        "aliases": ["u", "v", "w", "wind_speed", "WS", "wind_dir", "WD", "u*", "Ustar", "T_sonic", "Ts"],
        "description": "Anemometria sônica, componentes do vento e indicadores de turbulência.",
    },
    "Fluxos de Energia e Massa": {
        "aliases": ["H", "LE", "Fc", "co2_flux", "Tau", "NEE"],
        "description": "Fluxos turbulentos de calor, CO₂, água e quantidade de movimento.",
    },
    "Balanço de Radiação": {
        "aliases": ["SW_IN", "Rg", "SW_OUT", "LW_IN", "LW_OUT", "Rn", "NET", "PAR_in", "PPFD"],
        "description": "Componentes radiativos de onda curta, onda longa, saldo de radiação e PAR.",
    },
    "Variáveis Bioclimáticas e de Solo": {
        "aliases": ["Ta", "Tair", "AirTC", "RH", "rH", "VPD", "P", "PA", "Ts_1", "Ts_2", "Tsoil",
                    "SWC_1", "VWC", "G_1", "G_2"],
        "description": "Estado atmosférico próximo à superfície e condições térmicas/hídricas do solo.",
    },
    "Diagnósticos e Controle de Qualidade": {
        "aliases": ["qc_H", "qc_LE", "qc_Fc", "footprint_50", "footprint_90"],
        "description": "Indicadores QC/QA, diagnósticos e área de contribuição dos fluxos.",
    },
}

QC_CODE_COLORS = {
    0: "#1f77b4",
    1: "#ff7f0e",
    2: "#2ca02c",
    3: "#d62728",
    4: "#9467bd",
}

def qc_color(code):
    try:
        c = int(code)
    except Exception:
        return "#7f7f7f"
    return QC_CODE_COLORS.get(c, "#7f7f7f")

def base_name_for_grouping(name):
    n = str(name)
    suffixes = [
        "_orig", "_fall_qc", "_fqc", "_fall", "_fsdug", "_fsdu",
        "_fsd", "_fnum", "_fmeth", "_fwin", "_f", "_qc", "_sd"
    ]
    changed = True
    while changed:
        changed = False
        for s in suffixes:
            if n.lower().endswith(s.lower()):
                n = n[:-len(s)]
                changed = True
                break
    return n

def scientific_group(name):
    raw = str(name)
    base = base_name_for_grouping(raw)
    candidates = {raw.lower(), base.lower()}

    if is_qc(raw):
        return "Diagnósticos e Controle de Qualidade"

    if raw.lower() in TEMPORAL_FIELDS or base.lower() in TEMPORAL_FIELDS:
        return "Temporal e Identificação"

    for group, info in SCIENTIFIC_STRUCTURE.items():
        aliases = {str(a).lower() for a in info["aliases"]}
        if candidates & aliases:
            return group

    # Heurísticas para nomes compostos da planilha
    low = raw.lower()
    if any(k in low for k in ["wind", "ustar", "u*", "sonic", "tke", "tau"]):
        return "Ventos e Turbulência"
    if any(k in low for k in ["co2", "nee", "gpp", "reco", "h2o_flux", "latent", "sensible"]):
        return "Fluxos de Energia e Massa"
    if any(k in low for k in ["rad", "rg", "sw_", "lw_", "net", "par", "ppfd"]):
        return "Balanço de Radiação"
    if any(k in low for k in ["tair", "airtc", "rh", "vpd", "tsoil", "soil", "swc", "vwc", "precip", "press"]):
        return "Variáveis Bioclimáticas e de Solo"
    if any(k in low for k in ["footprint", "diag", "qc"]):
        return "Diagnósticos e Controle de Qualidade"

    return "Outras Variáveis / Produtos Derivados"

def grouped_physical_columns(df):
    groups = {}
    for c in physical_columns(df):
        g = scientific_group(c)
        groups.setdefault(g, []).append(c)
    return groups

VARIABLE_PALETTE = [
    "#1f77b4", "#d62728", "#2ca02c", "#9467bd", "#ff7f0e",
    "#17becf", "#8c564b", "#e377c2", "#bcbd22", "#7f7f7f",
    "#393b79", "#637939", "#8c6d31", "#843c39", "#7b4173",
]

def variable_color(var):
    text = str(var)
    idx = sum((i + 1) * ord(ch) for i, ch in enumerate(text)) % len(VARIABLE_PALETTE)
    return VARIABLE_PALETTE[idx]

def colors_for_variables(vars_):
    used, out = set(), {}
    for v in vars_:
        pref = variable_color(v)
        if pref not in used:
            col = pref
        else:
            col = next((c for c in VARIABLE_PALETTE if c not in used), pref)
        out[v] = col
        used.add(col)
    return out

def is_qc(name):
    n = str(name).lower()
    return any(t in n for t in QC_TOKENS)

def is_auxiliary(name):
    n = str(name).lower()
    return n.endswith(AUXILIARY_SUFFIXES)

def is_uncertainty(name):
    n = str(name).lower()
    return n.endswith(UNCERTAINTY_SUFFIXES)

def clean_numeric(series):
    s = pd.to_numeric(series, errors="coerce")
    return s.mask(s.isin(MISSING_SENTINELS))

@st.cache_data(show_spinner=False)
def load_original_workbook(uploaded_file):
    xls = pd.ExcelFile(uploaded_file)
    sheet = "output" if "output" in xls.sheet_names else xls.sheet_names[0]

    # Lê cabeçalho + linha de unidades separadamente.
    meta = pd.read_excel(uploaded_file, sheet_name=sheet, header=None, nrows=2)
    headers = [str(x).strip() for x in meta.iloc[0].tolist()]
    raw_units = meta.iloc[1].tolist()
    units = {
        h: str(u).strip()
        for h, u in zip(headers, raw_units)
        if pd.notna(u) and str(u).strip() not in {"", "-", "nan"}
    }

    # A segunda linha da planilha é de unidades, portanto é ignorada como dado.
    df = pd.read_excel(uploaded_file, sheet_name=sheet, header=0, skiprows=[1]).copy()

    time_candidates = [
        c for c in df.columns
        if str(c).strip().lower() in {"date time", "datetime", "date_time", "datatime", "timestamp"}
    ]
    if not time_candidates:
        raise ValueError("Não foi encontrada a coluna temporal da planilha.")

    time_col = time_candidates[0]
    df["TIMESTAMP"] = pd.to_datetime(df[time_col], errors="coerce")
    df = df[df["TIMESTAMP"].notna()].sort_values("TIMESTAMP").reset_index(drop=True)

    for c in df.columns:
        if c in {time_col, "TIMESTAMP"}:
            continue
        converted = pd.to_numeric(df[c], errors="coerce")
        if converted.notna().sum() > 0:
            # -9999 é marcador de ausência nesta planilha.
            df[c] = converted.mask(converted.isin(MISSING_SENTINELS))

    return df, sheet, time_col, units

def unit_only(var, units):
    u = units.get(var)
    if u is None or str(u).strip() == "":
        return "unidade não informada"
    return str(u).strip()

def unit_label(var, units):
    u = unit_only(var, units)
    return str(var) if u == "unidade não informada" else f"{var} [{u}]"

def valid_pct(s):
    return 100 * s.notna().mean() if len(s) else np.nan

def physical_columns(df):
    out = []
    for c in df.columns:
        n = str(c).strip().lower()
        if c == "TIMESTAMP" or n in TEMPORAL_FIELDS:
            continue
        if is_qc(c) or is_auxiliary(c):
            continue
        if pd.api.types.is_numeric_dtype(df[c]):
            out.append(c)
    return out

def qc_columns(df):
    return [
        c for c in df.columns
        if c != "TIMESTAMP" and is_qc(c) and pd.api.types.is_numeric_dtype(df[c])
    ]

def uncertainty_columns(df):
    return [
        c for c in df.columns
        if pd.api.types.is_numeric_dtype(df[c]) and is_uncertainty(c)
    ]

def period_controls(prefix, full_start, full_end):
    c1, c2, c3, c4 = st.columns(4)
    d1 = c1.date_input("Data inicial", value=full_start.date(), key=f"{prefix}_d1")
    t1 = c2.time_input("Hora inicial", value=full_start.time(), key=f"{prefix}_t1")
    d2 = c3.date_input("Data final", value=full_end.date(), key=f"{prefix}_d2")
    t2 = c4.time_input("Hora final", value=full_end.time(), key=f"{prefix}_t2")
    return pd.Timestamp.combine(d1, t1), pd.Timestamp.combine(d2, t2)

def filter_period(df, start, end):
    return df[(df["TIMESTAMP"] >= start) & (df["TIMESTAMP"] <= end)].copy()

def aggregate_numeric(df, vars_, resolution):
    d = df[["TIMESTAMP"] + vars_].copy().set_index("TIMESTAMP")
    if resolution == "30 min":
        return d.reset_index()
    rule = {
        "Horário": "1h",
        "Diário": "1D",
        "Semanal": "1W",
        "Mensal": "1MS",
    }[resolution]
    return d.resample(rule).mean(numeric_only=True).reset_index()

def valid_range(df, var):
    s = pd.to_numeric(df[var], errors="coerce")
    m = s.notna() & df["TIMESTAMP"].notna()
    if not m.any():
        return None, None, 0
    tt = df.loc[m, "TIMESTAMP"]
    return tt.min(), tt.max(), int(m.sum())

def line_plot(data, vars_, units, title, start=None, end=None):
    colors = colors_for_variables(vars_)
    fig = go.Figure()
    for v in vars_:
        fig.add_trace(go.Scattergl(
            x=data["TIMESTAMP"],
            y=data[v],
            mode="lines",
            name=unit_label(v, units),
            line=dict(color=colors[v], width=2),
            connectgaps=False,
        ))
    fig.update_layout(
        title=title,
        xaxis_title="Data e hora",
        yaxis_title="Valor",
        hovermode="x unified",
        height=480,
        margin=dict(l=20, r=20, t=55, b=20),
    )
    if start is not None and end is not None:
        fig.update_xaxes(range=[start, end])
    st.plotly_chart(fig, use_container_width=True)

def stats_table(df, vars_, units):
    rows = []
    for v in vars_:
        s = pd.to_numeric(df[v], errors="coerce")
        rows.append({
            "Variável": v,
            "Unidade": unit_only(v, units),
            "N válido": int(s.notna().sum()),
            "Disponibilidade (%)": round(valid_pct(s), 2),
            "Média": s.mean(),
            "Mediana": s.median(),
            "Desvio-padrão": s.std(),
            "Mínimo": s.min(),
            "Máximo": s.max(),
        })
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

def family_columns(df, base):
    candidates = [
        base, f"{base}_orig", f"{base}_f", f"{base}_fall",
        f"{base}_fsd", f"{base}_fqc", f"{base}_fall_qc",
        f"{base}_fnum", f"{base}_fmeth", f"{base}_fwin",
    ]
    return [c for c in candidates if c in df.columns]

def gapfill_status(df, base):
    orig = f"{base}_orig"
    filled = f"{base}_f"
    if orig not in df.columns or filled not in df.columns:
        return None

    a = pd.to_numeric(df[orig], errors="coerce")
    b = pd.to_numeric(df[filled], errors="coerce")
    measured = a.notna()
    filled_only = a.isna() & b.notna()
    missing = b.isna()

    return pd.Series(
        np.select(
            [measured, filled_only, missing],
            ["Observado", "Preenchido", "Ausente"],
            default="Ausente",
        ),
        index=df.index,
    )

def plot_observed_filled(df, base, units, start, end, resolution):
    orig = f"{base}_orig"
    filled = f"{base}_f"

    if orig not in df.columns or filled not in df.columns:
        st.info(f"A família {base} não possui simultaneamente {orig} e {filled}.")
        return

    sub = filter_period(df, start, end)
    if sub.empty:
        st.info("Sem registros no período selecionado.")
        return

    if resolution == "30 min":
        fig = go.Figure()
        obs = pd.to_numeric(sub[orig], errors="coerce")
        fil = pd.to_numeric(sub[filled], errors="coerce")
        filled_only = obs.isna() & fil.notna()

        fig.add_trace(go.Scattergl(
            x=sub["TIMESTAMP"], y=obs, mode="lines",
            name=f"{orig} — observado",
            line=dict(color="#1f77b4", width=1.5),
            connectgaps=False,
        ))
        fig.add_trace(go.Scattergl(
            x=sub.loc[filled_only, "TIMESTAMP"],
            y=fil.loc[filled_only],
            mode="markers",
            name=f"{filled} — preenchido onde {orig} está ausente",
            marker=dict(color="#d62728", size=5, symbol="circle"),
        ))
        fig.update_layout(
            title=f"{base}: observado × preenchido",
            xaxis_title="Data e hora",
            yaxis_title=unit_label(base, units),
            hovermode="closest",
            height=500,
            margin=dict(l=20, r=20, t=55, b=20),
        )
        fig.update_xaxes(range=[start, end])
        st.plotly_chart(fig, use_container_width=True)
    else:
        agg = aggregate_numeric(sub, [orig, filled], resolution)
        line_plot(
            agg, [orig, filled], units,
            f"{base}: observado × preenchido — {resolution.lower()}",
            start, end,
        )

    status = gapfill_status(sub, base)
    if status is not None:
        counts = status.value_counts()
        total = len(status)
        rows = []
        for k in ["Observado", "Preenchido", "Ausente"]:
            n = int(counts.get(k, 0))
            rows.append({
                "Situação": k,
                "Registros": n,
                "Percentual (%)": round(100*n/total, 2) if total else 0,
            })
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

def qc_code_table(series):
    s = pd.to_numeric(series, errors="coerce").dropna()
    if s.empty:
        return pd.DataFrame(columns=["Código QC", "N", "Percentual (%)", "Significado"])
    counts = s.value_counts().sort_index()
    total = counts.sum()
    rows = []
    for val, n in counts.items():
        disp = int(val) if float(val).is_integer() else val
        rows.append({
            "Código QC": disp,
            "N": int(n),
            "Percentual (%)": round(100*int(n)/total, 2),
            "Significado": "Não documentado na planilha",
        })
    return pd.DataFrame(rows)

# ============================================================
# Sidebar / carga
# ============================================================

st.sidebar.title("EcoFlux Brasil")
st.sidebar.caption("Plataforma científica para séries micrometeorológicas e Eddy Covariance")

uploaded = st.sidebar.file_uploader(
    "Carregar planilha original",
    type=["xlsx"],
    help="Estrutura esperada: planilha output, cabeçalho na primeira linha e unidades na segunda.",
)

if uploaded is None:
    st.title("EcoFlux Brasil")
    st.info(
        "Carregue a planilha original para iniciar. A V22 foi estruturada para o arquivo "
        "`dados_preenchidos 4-6-25 a 2-4-26.xlsx`."
    )
    st.stop()

try:
    df, sheet_name, time_col, units = load_original_workbook(uploaded)
except Exception as exc:
    st.error(f"Não foi possível carregar a planilha: {exc}")
    st.stop()

full_start = df["TIMESTAMP"].min()
full_end = df["TIMESTAMP"].max()
phys_vars = physical_columns(df)
qc_vars = qc_columns(df)
unc_vars = uncertainty_columns(df)

page = st.sidebar.radio(
    "Navegação",
    [
        "Visão Geral",
        "Estrutura Científica",
        "Séries Científicas",
        "Comparar Variáveis",
        "Preenchimento de Lacunas",
        "Balanço de Carbono",
        "Qualidade dos Dados",
        "Sobre os Dados",
        "Solicitar Dados",
    ],
)

st.sidebar.success(
    f"{len(df):,} registros | {full_start:%d/%m/%Y} → {full_end:%d/%m/%Y}".replace(",", ".")
)

# ============================================================
# Páginas
# ============================================================

if page == "Visão Geral":
    st.title("EcoFlux Brasil")
    st.subheader("Dados originais de processamento")

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Registros", f"{len(df):,}".replace(",", "."))
    c2.metric("Variáveis físicas/produtos", len(phys_vars))
    c3.metric("Indicadores QC", len(qc_vars))
    c4.metric("Planilha", sheet_name)

    st.markdown(
        f"**Cobertura temporal:** {full_start:%d/%m/%Y %H:%M} → "
        f"{full_end:%d/%m/%Y %H:%M}"
    )

    st.info(
        "Nesta versão, `-9999` é tratado como marcador de ausência de dado. "
        "Campos temporais e indicadores QC não são classificados como grandezas físicas."
    )

    family_rows = []
    for base in GAPFILL_FAMILIES:
        cols = family_columns(df, base)
        if cols:
            family_rows.append({
                "Família": base,
                "Unidade base": unit_only(base, units),
                "Produtos encontrados": ", ".join(cols),
            })
    st.subheader("Organização científica")
    grouped = grouped_physical_columns(df)
    structure_rows = []
    for group, vals in grouped.items():
        structure_rows.append({
            "Grupo": group,
            "Variáveis/produtos identificados": len(vals),
        })
    st.dataframe(pd.DataFrame(structure_rows), use_container_width=True, hide_index=True)

    st.subheader("Famílias de processamento identificadas")
    st.dataframe(pd.DataFrame(family_rows), use_container_width=True, hide_index=True)


elif page == "Estrutura Científica":
    st.header("Estrutura Científica dos Dados")
    st.write(
        "O EcoFlux organiza as variáveis segundo a estrutura típica de uma torre micrometeorológica. "
        "Essa classificação melhora a navegação, mas não altera nomes, valores ou unidades da planilha."
    )

    st.info(
        "As unidades mostradas nas análises são sempre lidas do arquivo original quando disponíveis. "
        "As unidades típicas abaixo funcionam apenas como referência científica e não substituem os metadados da fonte."
    )

    grouped = grouped_physical_columns(df)

    typical_units = {
        "Ventos e Turbulência": "m/s; graus; temperatura sônica em °C ou K, conforme a fonte",
        "Fluxos de Energia e Massa": "H e LE tipicamente W/m²; fluxos de CO₂ tipicamente µmol m⁻² s⁻¹; Tau tipicamente Pa",
        "Balanço de Radiação": "componentes radiativos tipicamente W/m²; PAR/PPFD tipicamente µmol m⁻² s⁻¹",
        "Variáveis Bioclimáticas e de Solo": "temperatura, umidade, VPD, pressão, água no solo e fluxo de calor conforme o sensor/fonte",
        "Diagnósticos e Controle de Qualidade": "QC sem unidade; footprint tipicamente em metros quando aplicável",
        "Outras Variáveis / Produtos Derivados": "conforme metadados da planilha",
    }

    for group in [
        "Ventos e Turbulência",
        "Fluxos de Energia e Massa",
        "Balanço de Radiação",
        "Variáveis Bioclimáticas e de Solo",
        "Diagnósticos e Controle de Qualidade",
        "Outras Variáveis / Produtos Derivados",
    ]:
        with st.expander(group, expanded=(group in ["Fluxos de Energia e Massa", "Balanço de Radiação"])):
            info = SCIENTIFIC_STRUCTURE.get(group, {})
            if info.get("description"):
                st.write(info["description"])
            st.caption(f"Referência típica: {typical_units[group]}")

            vars_here = grouped.get(group, [])
            if group == "Diagnósticos e Controle de Qualidade":
                vars_here = sorted(set(vars_here + qc_vars))

            if not vars_here:
                st.write("Nenhuma variável desta categoria foi identificada no arquivo atual.")
            else:
                rows = []
                for v in vars_here:
                    first, last, n = valid_range(df, v)
                    rows.append({
                        "Variável": v,
                        "Unidade da fonte": "sem unidade" if is_qc(v) else unit_only(v, units),
                        "Primeiro registro disponível": first.strftime("%d/%m/%Y %H:%M") if first is not None else "—",
                        "Último registro disponível": last.strftime("%d/%m/%Y %H:%M") if last is not None else "—",
                        "N disponível": n,
                    })
                st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

elif page == "Séries Científicas":
    st.header("Séries Científicas")

    groups = grouped_physical_columns(df)
    group_options = [g for g, vals in groups.items() if vals]
    selected_group = st.selectbox(
        "Grupo científico",
        group_options,
        key="single_group_v23",
    )
    vars_group = groups[selected_group]
    var = st.selectbox(
        "Variável/produto científico",
        vars_group,
        format_func=lambda x: unit_label(x, units),
        key="single_var_v23",
    )
    start, end = period_controls("single", full_start, full_end)
    resolution = st.selectbox(
        "Resolução",
        ["30 min", "Horário", "Diário", "Semanal", "Mensal"],
        index=0,
        key="single_res",
    )

    if start > end:
        st.error("O início deve ser anterior ao fim.")
    else:
        sub = filter_period(df, start, end)
        a, b, n = valid_range(df, var)
        if a is not None:
            st.caption(
                f"Disponibilidade de {var}: {a:%d/%m/%Y %H:%M} → {b:%d/%m/%Y %H:%M} | "
                f"{n:,} valores disponíveis".replace(",", ".")
            )
        data = aggregate_numeric(sub, [var], resolution)
        line_plot(data, [var], units, unit_label(var, units), start, end)
        stats_table(sub, [var], units)

elif page == "Comparar Variáveis":
    st.header("Comparar Variáveis")
    st.caption("Indicadores QC não aparecem nesta lista; eles ficam em Qualidade dos Dados.")

    vars_ = st.multiselect(
        "Variáveis/produtos",
        phys_vars,
        format_func=lambda x: unit_label(x, units),
    )
    start, end = period_controls("compare", full_start, full_end)
    resolution = st.selectbox(
        "Resolução",
        ["30 min", "Horário", "Diário", "Semanal", "Mensal"],
        index=2,
        key="compare_res",
    )

    if len(vars_) < 2:
        st.info("Selecione pelo menos duas variáveis.")
    elif start > end:
        st.error("O início deve ser anterior ao fim.")
    else:
        sub = filter_period(df, start, end)
        data = aggregate_numeric(sub, vars_, resolution)
        line_plot(data, vars_, units, "Comparação de variáveis", start, end)
        stats_table(sub, vars_, units)

        corr = data[vars_].corr(method="pearson", min_periods=3)
        st.subheader("Correlação de Pearson")
        fig = px.imshow(corr, text_auto=".2f", aspect="auto", zmin=-1, zmax=1)
        st.plotly_chart(fig, use_container_width=True)
        st.caption("Correlação não implica causalidade.")

elif page == "Preenchimento de Lacunas":
    st.header("Preenchimento de Lacunas")
    st.write(
        "Esta página separa explicitamente valores observados (`_orig`) de valores da série "
        "preenchida (`_f`). Em 30 min, os pontos preenchidos onde o original está ausente "
        "são destacados no gráfico."
    )

    available_families = [
        b for b in GAPFILL_FAMILIES
        if f"{b}_orig" in df.columns and f"{b}_f" in df.columns
    ]
    base = st.selectbox("Família", available_families)
    start, end = period_controls("gap", full_start, full_end)
    resolution = st.selectbox(
        "Resolução",
        ["30 min", "Horário", "Diário", "Semanal", "Mensal"],
        index=0,
        key="gap_res",
    )

    if start <= end:
        plot_observed_filled(df, base, units, start, end, resolution)

        related = family_columns(df, base)
        st.subheader("Produtos da família")
        rel_rows = []
        for c in related:
            rel_rows.append({
                "Campo": c,
                "Tipo": (
                    "Qualidade/flag" if is_qc(c)
                    else "Auxiliar de preenchimento" if is_auxiliary(c)
                    else "Incerteza" if is_uncertainty(c)
                    else "Série física/produto"
                ),
                "Unidade": "sem unidade" if is_qc(c) else unit_only(c, units),
            })
        st.dataframe(pd.DataFrame(rel_rows), use_container_width=True, hide_index=True)

elif page == "Balanço de Carbono":
    st.header("Balanço de Carbono")

    carbon_candidates = [
        c for c in [
            "NEE", "NEE_orig", "NEE_f", "NEE_fall",
            "NEE_U05_f", "NEE_U50_f", "NEE_U95_f",
            "Reco", "GPP_f", "FP_NEEnight", "R_ref",
        ]
        if c in df.columns
    ]

    selected = st.multiselect(
        "Produtos de carbono",
        carbon_candidates,
        default=[c for c in ["NEE_f", "Reco", "GPP_f"] if c in carbon_candidates],
        format_func=lambda x: unit_label(x, units),
    )
    start, end = period_controls("carbon", full_start, full_end)
    resolution = st.selectbox(
        "Resolução",
        ["30 min", "Horário", "Diário", "Semanal", "Mensal"],
        index=2,
        key="carbon_res",
    )

    if selected and start <= end:
        sub = filter_period(df, start, end)
        data = aggregate_numeric(sub, selected, resolution)
        line_plot(data, selected, units, "Produtos de carbono", start, end)
        stats_table(sub, selected, units)

        nee_unc = [
            c for c in ["NEE_fsd", "NEE_fsdu", "NEE_fsdug"]
            if c in df.columns
        ]
        if nee_unc:
            st.subheader("Produtos de incerteza associados ao NEE")
            st.dataframe(
                pd.DataFrame({
                    "Campo": nee_unc,
                    "Unidade": [unit_only(c, units) for c in nee_unc],
                }),
                use_container_width=True,
                hide_index=True,
            )

elif page == "Qualidade dos Dados":
    st.header("Qualidade dos Dados")
    st.write(
        "Todos os indicadores QC/QA ficam concentrados nesta página. "
        "As cores servem apenas para distinguir códigos e não representam automaticamente uma escala de bom/ruim."
    )

    st.warning(
        "A planilha apresenta códigos diferentes entre famílias, incluindo 0, 1, 2, 3 e, em alguns indicadores, 4. "
        "Enquanto a documentação específica do processamento não for vinculada ao EcoFlux, o significado científico "
        "de cada código permanece como 'não documentado na planilha'."
    )

    qc = st.selectbox("Indicador QC", qc_vars, key="qc_select_v23")
    start, end = period_controls("qc_v23", full_start, full_end)

    if start <= end:
        sub = filter_period(df, start, end)
        s = pd.to_numeric(sub[qc], errors="coerce").dropna()

        a, b, n = valid_range(df, qc)
        if a is not None:
            st.caption(
                f"Disponibilidade de {qc}: {a:%d/%m/%Y %H:%M} → {b:%d/%m/%Y %H:%M} | "
                f"{n:,} registros disponíveis no arquivo".replace(",", ".")
            )

        table = qc_code_table(s)

        if not table.empty:
            dominant_row = table.sort_values(["N", "Código QC"], ascending=[False, True]).iloc[0]
            dominant_code = dominant_row["Código QC"]
            dominant_pct = dominant_row["Percentual (%)"]
            num_codes = table["Código QC"].nunique()
            total_available = int(table["N"].sum())

            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Código predominante", str(dominant_code))
            c2.metric("Participação do predominante", f"{dominant_pct:.2f}%")
            c3.metric("Códigos encontrados", int(num_codes))
            c4.metric("Registros QC disponíveis", f"{total_available:,}".replace(",", "."))

        st.subheader("Distribuição dos códigos")
        st.dataframe(table, use_container_width=True, hide_index=True)

        if not table.empty:
            bar_colors = [qc_color(x) for x in table["Código QC"]]
            fig = go.Figure()
            fig.add_trace(go.Bar(
                x=[str(x) for x in table["Código QC"]],
                y=table["Percentual (%)"],
                text=[f"{x:.2f}%" for x in table["Percentual (%)"]],
                textposition="outside",
                marker=dict(color=bar_colors),
                customdata=np.column_stack([table["N"], table["Significado"]]),
                hovertemplate=(
                    "Código QC: %{x}<br>"
                    "Percentual: %{y:.2f}%<br>"
                    "N: %{customdata[0]}<br>"
                    "Significado: %{customdata[1]}"
                    "<extra></extra>"
                ),
                showlegend=False,
            ))
            fig.update_layout(
                title=f"Distribuição de {qc}",
                xaxis_title="Código QC (sem unidade)",
                yaxis_title="Percentual dos registros (%)",
                height=420,
                margin=dict(l=20, r=20, t=55, b=20),
            )
            st.plotly_chart(fig, use_container_width=True)

        st.subheader("QC ao longo do tempo")
        st.caption(
            "Cada cor identifica somente um código QC. A cor não implica, por si só, qualidade superior ou inferior."
        )

        qdf = sub[["TIMESTAMP", qc]].copy()
        qdf[qc] = pd.to_numeric(qdf[qc], errors="coerce")
        observed_codes = sorted(qdf[qc].dropna().unique().tolist())

        fig2 = go.Figure()
        for code_val in observed_codes:
            mask = qdf[qc] == code_val
            label = str(int(code_val)) if float(code_val).is_integer() else str(code_val)
            fig2.add_trace(go.Scattergl(
                x=qdf.loc[mask, "TIMESTAMP"],
                y=qdf.loc[mask, qc],
                mode="markers",
                name=f"Código {label}",
                marker=dict(
                    size=6,
                    color=qc_color(code_val),
                    symbol="circle",
                ),
                hovertemplate=(
                    "Data: %{x}<br>"
                    f"Código QC: {label}<br>"
                    "Significado: não documentado na planilha"
                    "<extra></extra>"
                ),
            ))

        fig2.update_layout(
            xaxis_title="Data e hora",
            yaxis=dict(
                title="Código QC (sem unidade)",
                tickmode="array",
                tickvals=observed_codes,
                ticktext=[
                    str(int(x)) if float(x).is_integer() else str(x)
                    for x in observed_codes
                ],
            ),
            legend_title="Identificação visual",
            height=450,
            margin=dict(l=20, r=20, t=30, b=20),
        )
        fig2.update_xaxes(range=[start, end])
        st.plotly_chart(fig2, use_container_width=True)

        st.subheader("Legenda visual dos códigos")
        legend_df = pd.DataFrame([
            {
                "Código QC": int(x) if float(x).is_integer() else x,
                "Cor": qc_color(x),
                "Interpretação no EcoFlux": "Código identificado; significado científico ainda não documentado",
            }
            for x in observed_codes
        ])
        st.dataframe(legend_df, use_container_width=True, hide_index=True)

elif page == "Sobre os Dados":
    st.header("Sobre os Dados")
    st.markdown(
        f"""
### Fonte atual
A V22 foi desenhada para a estrutura da planilha original carregada nesta sessão.

- **Planilha:** `{sheet_name}`
- **Coluna temporal:** `{time_col}`
- **Cobertura:** {full_start:%d/%m/%Y %H:%M} → {full_end:%d/%m/%Y %H:%M}
- **Registros:** {len(df):,}
- **Campos totais:** {len([c for c in df.columns if c != "TIMESTAMP"])}

### Regras de interpretação
`-9999` é tratado como ausência de dado. A linha de unidades da planilha é lida como metadado,
não como observação. Campos `QC` são mantidos sem unidade e não recebem significado textual
quando esse significado não está documentado no próprio arquivo.

### Famílias
Para NEE, LE, H, Rg, VPD, rH, Tair e Tsoil, o EcoFlux reconhece automaticamente produtos
como `_orig`, `_f`, `_fall`, `_fsd`, `_fqc`, `_fall_qc`, `_fnum`, `_fmeth` e `_fwin`.
"""
    )

elif page == "Solicitar Dados":
    st.header("Solicitar Dados")
    st.write(
        "Os dados brutos não são disponibilizados para download público direto. "
        "Solicitações devem ser avaliadas e autorizadas pelo responsável pelo conjunto de dados."
    )

    with st.form("request_form"):
        nome = st.text_input("Nome")
        email = st.text_input("E-mail")
        instituicao = st.text_input("Instituição")
        finalidade = st.text_area("Finalidade científica / uso pretendido")
        periodo = st.text_input("Período de interesse")
        variaveis = st.text_area("Variáveis de interesse")
        submitted = st.form_submit_button("Preparar solicitação")

    if submitted:
        st.success(
            "Solicitação preparada. Esta versão demonstrativa não envia nem armazena o formulário "
            "automaticamente; a autorização deve ocorrer pelo responsável pelos dados."
        )
