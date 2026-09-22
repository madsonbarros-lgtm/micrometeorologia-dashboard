import csv
import base64
import io
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import streamlit as st

st.set_page_config(
    page_title="Carbono em Ação",
    page_icon="🌿",
    layout="wide",
)

st.markdown(
    """
    <style>
    :root {
        --ecoflux-green: #218838;
        --ecoflux-green-soft: #eef8ef;
        --ecoflux-blue-soft: #eef6ff;
        --ecoflux-yellow-soft: #fff7e6;
        --ecoflux-border: rgba(120, 120, 120, .20);
        --ecoflux-text: #202124;
        --ecoflux-muted: #69707a;
    }

    .block-container {
        padding-top: 1.35rem;
        padding-bottom: 2rem;
        max-width: 1500px;
    }

    section[data-testid="stSidebar"] {
        background: #f6f7f8;
    }

    section[data-testid="stSidebar"] > div {
        padding-top: 1.15rem;
    }

    .ecoflux-hero {
        font-size: 2.85rem;
        line-height: 1.0;
        font-weight: 800;
        color: var(--ecoflux-green);
        margin: .35rem 0 1.05rem 0;
        letter-spacing: -0.035em;
    }

    .ecoflux-success {
        padding: 1rem 1.15rem;
        border-radius: 10px;
        background: linear-gradient(90deg, #edf8ee 0%, #f4fbf4 100%);
        border: 1px solid #d7ebd9;
        margin: 0 0 1.05rem 0;
    }

    .ecoflux-success-line {
        display: flex;
        align-items: center;
        gap: .55rem;
        color: #1d6f35;
        font-weight: 700;
        font-size: 1rem;
        margin-bottom: .28rem;
    }

    .ecoflux-success-sub {
        color: #5b6d5f;
        font-size: .92rem;
        margin-left: 1.85rem;
    }

    .ecoflux-section-title {
        font-size: 1.25rem;
        font-weight: 750;
        color: var(--ecoflux-text);
        margin: 1.05rem 0 .7rem 0;
    }

    .ecoflux-summary-wrap {
        border: 1px solid var(--ecoflux-border);
        border-radius: 10px;
        overflow: hidden;
        margin-bottom: .85rem;
        background: #fff;
    }

    .ecoflux-summary {
        width: 100%;
        border-collapse: collapse;
        font-size: .90rem;
    }

    .ecoflux-summary th {
        text-align: left;
        padding: .7rem .75rem;
        background: #f8f9fa;
        border-bottom: 1px solid var(--ecoflux-border);
        color: #3f454c;
        font-weight: 600;
    }

    .ecoflux-summary td {
        padding: .72rem .75rem;
        border-bottom: 1px solid rgba(128,128,128,.12);
        vertical-align: top;
        color: #2d3136;
    }

    .ecoflux-summary tr:last-child td {
        border-bottom: none;
    }

    .resolution-pill {
        display: inline-block;
        padding: .18rem .5rem;
        border-radius: 7px;
        background: #dff2df;
        color: #26743b;
        font-weight: 700;
        font-size: .82rem;
    }

    .ok-status {
        color: #2f8b46;
        font-weight: 700;
        white-space: nowrap;
    }

    .ecoflux-info {
        padding: .78rem 1rem;
        border-radius: 10px;
        background: var(--ecoflux-blue-soft);
        border: 1px solid #d8e9f9;
        margin: .75rem 0 1.15rem 0;
        color: #336c9e;
        font-size: .92rem;
    }

    .ecoflux-actions {
        display: grid;
        grid-template-columns: repeat(4, minmax(0, 1fr));
        gap: .75rem;
        margin-top: .45rem;
        margin-bottom: .95rem;
    }

    .ecoflux-action-card {
        display: flex;
        align-items: center;
        gap: .8rem;
        padding: .95rem 1rem;
        min-height: 90px;
        border: 1px solid var(--ecoflux-border);
        border-radius: 11px;
        background: #fff;
        box-shadow: 0 1px 2px rgba(0,0,0,.02);
    }

    .ecoflux-action-icon {
        width: 34px;
        min-width: 34px;
        height: 34px;
        display: flex;
        align-items: center;
        justify-content: center;
    }

    .ecoflux-action-text h4 {
        margin: 0 0 .22rem 0;
        font-size: .98rem;
        font-weight: 700;
        color: #202124;
        line-height: 1.2;
    }

    .ecoflux-action-text p {
        margin: 0;
        color: #656d76;
        line-height: 1.35;
        font-size: .84rem;
    }

    .ecoflux-tip {
        padding: .78rem 1rem;
        border-radius: 10px;
        background: var(--ecoflux-yellow-soft);
        border: 1px solid #f5e5bd;
        color: #b87913;
        font-size: .90rem;
        margin-top: .4rem;
        margin-bottom: 1.1rem;
    }

    .ecoflux-gap-warning {
        padding: .8rem 1rem;
        border-radius: 10px;
        background: #fff9dd;
        border: 1px solid #efe2a3;
        color: #9b7412;
        margin-bottom: .75rem;
        font-size: .90rem;
    }

    .sidebar-status {
        padding: .72rem .8rem;
        border-radius: 9px;
        background: #e9f7ea;
        border: 1px solid #d6ead8;
        margin: .45rem 0;
        font-size: .86rem;
        color: #2d6e3a;
    }

    @media (max-width: 1100px) {
        .ecoflux-actions {
            grid-template-columns: repeat(2, minmax(0, 1fr));
        }
    }

    @media (max-width: 700px) {
        .ecoflux-actions {
            grid-template-columns: 1fr;
        }
        .ecoflux-hero {
            font-size: 2.2rem;
        }
    }
    
.ca-brand-inline{display:flex;align-items:center;gap:14px!important}
.ca-brand-logo{width:68px;height:68px;display:flex;align-items:center;justify-content:center;color:#43ef92;flex:0 0 68px}
.ca-brand-logo svg{width:68px;height:68px;stroke-width:1.9}
.ca-brand-copy{display:block}
[data-testid="stButton"] button p,
[data-testid="stPopover"] button p{display:flex!important;align-items:center!important;justify-content:center!important;gap:9px!important}
.ca-nav-ico{display:inline-flex;align-items:center;justify-content:center;width:24px;height:24px;vertical-align:middle}
.ca-nav-ico svg{width:23px;height:23px;stroke-width:2.1}

/* ÍCONES DO CABEÇALHO — vetoriais, maiores e independentes da fonte */
div[data-testid="stHorizontalBlock"]:has(.header-anchor) [data-testid="stColumn"]:nth-child(n+2) button p::before{
 content:"";display:inline-block!important;width:25px!important;height:25px!important;
 min-width:25px!important;margin-right:9px!important;background:#fff!important;
 -webkit-mask-repeat:no-repeat!important;mask-repeat:no-repeat!important;
 -webkit-mask-position:center!important;mask-position:center!important;
 -webkit-mask-size:25px 25px!important;mask-size:25px 25px!important;
 vertical-align:-6px!important;
}
/* casa */
div[data-testid="stHorizontalBlock"]:has(.header-anchor) [data-testid="stColumn"]:nth-child(2) button p::before{
 -webkit-mask-image:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='black' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpath d='m3 11 9-8 9 8'/%3E%3Cpath d='M5 10v10h14V10'/%3E%3Cpath d='M9 20v-6h6v6'/%3E%3C/svg%3E");mask-image:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='black' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpath d='m3 11 9-8 9 8'/%3E%3Cpath d='M5 10v10h14V10'/%3E%3Cpath d='M9 20v-6h6v6'/%3E%3C/svg%3E")
}
/* gráfico */
div[data-testid="stHorizontalBlock"]:has(.header-anchor) [data-testid="stColumn"]:nth-child(3) button p::before{
 -webkit-mask-image:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='black' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpath d='M3 3v18h18'/%3E%3Cpath d='M7 16v-5M12 16V8M17 16V5'/%3E%3C/svg%3E");mask-image:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='black' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpath d='M3 3v18h18'/%3E%3Cpath d='M7 16v-5M12 16V8M17 16V5'/%3E%3C/svg%3E")
}
/* banco de dados */
div[data-testid="stHorizontalBlock"]:has(.header-anchor) [data-testid="stColumn"]:nth-child(4) button p::before{
 -webkit-mask-image:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='black' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'%3E%3Cellipse cx='12' cy='5' rx='8' ry='3'/%3E%3Cpath d='M4 5v6c0 1.7 3.6 3 8 3s8-1.3 8-3V5M4 11v6c0 1.7 3.6 3 8 3s8-1.3 8-3v-6'/%3E%3C/svg%3E");mask-image:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='black' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'%3E%3Cellipse cx='12' cy='5' rx='8' ry='3'/%3E%3Cpath d='M4 5v6c0 1.7 3.6 3 8 3s8-1.3 8-3V5M4 11v6c0 1.7 3.6 3 8 3s8-1.3 8-3v-6'/%3E%3C/svg%3E")
}
/* análises */
div[data-testid="stHorizontalBlock"]:has(.header-anchor) [data-testid="stColumn"]:nth-child(5) button p::before{
 -webkit-mask-image:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='black' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpath d='m3 17 5-5 4 3 7-8'/%3E%3Ccircle cx='3' cy='17' r='1.5'/%3E%3Ccircle cx='8' cy='12' r='1.5'/%3E%3Ccircle cx='12' cy='15' r='1.5'/%3E%3Ccircle cx='19' cy='7' r='1.5'/%3E%3C/svg%3E");mask-image:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='black' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpath d='m3 17 5-5 4 3 7-8'/%3E%3Ccircle cx='3' cy='17' r='1.5'/%3E%3Ccircle cx='8' cy='12' r='1.5'/%3E%3Ccircle cx='12' cy='15' r='1.5'/%3E%3Ccircle cx='19' cy='7' r='1.5'/%3E%3C/svg%3E")
}
/* escudo */
div[data-testid="stHorizontalBlock"]:has(.header-anchor) [data-testid="stColumn"]:nth-child(6) button p::before{
 -webkit-mask-image:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='black' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpath d='M12 3 20 6v6c0 5-3.5 8-8 10-4.5-2-8-5-8-10V6l8-3Z'/%3E%3Cpath d='M12 7v10M9 10h6'/%3E%3C/svg%3E");mask-image:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='black' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpath d='M12 3 20 6v6c0 5-3.5 8-8 10-4.5-2-8-5-8-10V6l8-3Z'/%3E%3Cpath d='M12 7v10M9 10h6'/%3E%3C/svg%3E")
}
/* informação */
div[data-testid="stHorizontalBlock"]:has(.header-anchor) [data-testid="stColumn"]:nth-child(7) button p::before{
 -webkit-mask-image:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='black' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'%3E%3Ccircle cx='12' cy='12' r='9'/%3E%3Cpath d='M12 11v6M12 7h.01'/%3E%3C/svg%3E");mask-image:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='black' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'%3E%3Ccircle cx='12' cy='12' r='9'/%3E%3Cpath d='M12 11v6M12 7h.01'/%3E%3C/svg%3E")
}
/* upload nuvem */
div[data-testid="stHorizontalBlock"]:has(.header-anchor) [data-testid="stColumn"]:nth-child(8) button p::before{
 -webkit-mask-image:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='black' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpath d='M16 16l-4-4-4 4M12 12v8'/%3E%3Cpath d='M20 17.5A4.5 4.5 0 0 0 18 9a7 7 0 0 0-13.5 2A4 4 0 0 0 5 19h3'/%3E%3C/svg%3E");mask-image:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='black' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpath d='M16 16l-4-4-4 4M12 12v8'/%3E%3Cpath d='M20 17.5A4.5 4.5 0 0 0 18 9a7 7 0 0 0-13.5 2A4 4 0 0 0 5 19h3'/%3E%3C/svg%3E")
}
/* globo */
div[data-testid="stHorizontalBlock"]:has(.header-anchor) [data-testid="stColumn"]:nth-child(9) button p::before{
 -webkit-mask-image:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='black' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'%3E%3Ccircle cx='12' cy='12' r='9'/%3E%3Cpath d='M3 12h18M12 3c3 3 4 6 4 9s-1 6-4 9c-3-3-4-6-4-9s1-6 4-9Z'/%3E%3C/svg%3E");mask-image:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='black' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'%3E%3Ccircle cx='12' cy='12' r='9'/%3E%3Cpath d='M3 12h18M12 3c3 3 4 6 4 9s-1 6-4 9c-3-3-4-6-4-9s1-6 4-9Z'/%3E%3C/svg%3E")
}
/* engrenagem */
div[data-testid="stHorizontalBlock"]:has(.header-anchor) [data-testid="stColumn"]:nth-child(10) button p::before{
 -webkit-mask-image:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='black' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'%3E%3Ccircle cx='12' cy='12' r='3'/%3E%3Cpath d='M19.4 15a1.7 1.7 0 0 0 .34 1.88l.06.06-2.83 2.83-.06-.06a1.7 1.7 0 0 0-1.88-.34 1.7 1.7 0 0 0-1.03 1.56V21h-4v-.09A1.7 1.7 0 0 0 9 19.36a1.7 1.7 0 0 0-1.88.34l-.06.06-2.83-2.83.06-.06A1.7 1.7 0 0 0 4.63 15 1.7 1.7 0 0 0 3.08 14H3v-4h.09A1.7 1.7 0 0 0 4.64 9a1.7 1.7 0 0 0-.34-1.88l-.06-.06 2.83-2.83.06.06A1.7 1.7 0 0 0 9 4.63 1.7 1.7 0 0 0 10 3.08V3h4v.09A1.7 1.7 0 0 0 15 4.64a1.7 1.7 0 0 0 1.88-.34l.06-.06 2.83 2.83-.06.06A1.7 1.7 0 0 0 19.37 9 1.7 1.7 0 0 0 20.92 10H21v4h-.09A1.7 1.7 0 0 0 19.4 15Z'/%3E%3C/svg%3E");mask-image:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='black' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'%3E%3Ccircle cx='12' cy='12' r='3'/%3E%3Cpath d='M19.4 15a1.7 1.7 0 0 0 .34 1.88l.06.06-2.83 2.83-.06-.06a1.7 1.7 0 0 0-1.88-.34 1.7 1.7 0 0 0-1.03 1.56V21h-4v-.09A1.7 1.7 0 0 0 9 19.36a1.7 1.7 0 0 0-1.88.34l-.06.06-2.83-2.83.06-.06A1.7 1.7 0 0 0 4.63 15 1.7 1.7 0 0 0 3.08 14H3v-4h.09A1.7 1.7 0 0 0 4.64 9a1.7 1.7 0 0 0-.34-1.88l-.06-.06 2.83-2.83.06.06A1.7 1.7 0 0 0 9 4.63 1.7 1.7 0 0 0 10 3.08V3h4v.09A1.7 1.7 0 0 0 15 4.64a1.7 1.7 0 0 0 1.88-.34l.06-.06 2.83 2.83-.06.06A1.7 1.7 0 0 0 19.37 9 1.7 1.7 0 0 0 20.92 10H21v4h-.09A1.7 1.7 0 0 0 19.4 15Z'/%3E%3C/svg%3E")
}

/* ===== CABEÇALHO v13: uniforme como a referência ===== */
div[data-testid="stHorizontalBlock"]:has(.header-anchor) button{
    background:transparent!important;
    border:1px solid transparent!important;
    box-shadow:none!important;
    outline:none!important;
}
div[data-testid="stHorizontalBlock"]:has(.header-anchor) button:hover{
    background:rgba(18,181,105,.18)!important;
    border-color:transparent!important;
}
div[data-testid="stHorizontalBlock"]:has(.header-anchor) button:focus,
div[data-testid="stHorizontalBlock"]:has(.header-anchor) button:focus-visible{
    box-shadow:none!important;
    outline:none!important;
}
/* remove o destaque permanente de Início e o contorno exclusivo de Arquivos */
div[data-testid="stHorizontalBlock"]:has(.header-anchor) [data-testid="stColumn"]:nth-child(2) button,
div[data-testid="stHorizontalBlock"]:has(.header-anchor) [data-testid="stColumn"]:nth-child(8) button{
    background:transparent!important;
    border-color:transparent!important;
}
/* remove o chevron nativo/subscrito dos popovers */
div[data-testid="stHorizontalBlock"]:has(.header-anchor) [data-testid="stPopover"] button svg:last-child{
    display:none!important;
}
/* alinhamento uniforme dos rótulos e desenhos */
div[data-testid="stHorizontalBlock"]:has(.header-anchor) button p{
    display:flex!important;
    align-items:center!important;
    justify-content:center!important;
    gap:8px!important;
    margin:0!important;
    line-height:1.15!important;
}

/* Símbolo oficial CARBONO EM AÇÃO — imagem fornecida pelo usuário, sem redesenho */
.ca-brand-logo-real{
    width:76px!important;
    min-width:76px!important;
    height:66px!important;
    display:flex!important;
    align-items:center!important;
    justify-content:center!important;
    overflow:visible!important;
}
.ca-brand-logo-real img{
    display:block!important;
    width:72px!important;
    height:auto!important;
    max-height:64px!important;
    object-fit:contain!important;
    image-rendering:auto!important;
}
</style>
    """,
    unsafe_allow_html=True,
)


st.markdown("""
<style>
/* CARBONO EM AÇÃO — SOMENTE APARÊNCIA.
   Nenhuma regra abaixo altera rotas, cálculos, callbacks ou páginas. */
section[data-testid="stSidebar"]{
    background:linear-gradient(180deg,#003d2e 0%,#004735 58%,#00392c 100%)!important;
    border-right:1px solid rgba(80,235,140,.15)!important;
}
section[data-testid="stSidebar"] label,
section[data-testid="stSidebar"] p,
section[data-testid="stSidebar"] h1,
section[data-testid="stSidebar"] h2,
section[data-testid="stSidebar"] h3{
    color:#f4fff7!important;
}
section[data-testid="stSidebar"] [data-testid="stFileUploader"]{
    background:#07553e!important;
    border:1px solid rgba(83,239,143,.24)!important;
    border-radius:10px!important;
    padding:.45rem!important;
}
section[data-testid="stSidebar"] [data-testid="stFileUploaderDropzone"]{
    background:#086047!important;
    border-color:rgba(105,245,159,.25)!important;
}
section[data-testid="stSidebar"] [data-testid="stFileUploaderDropzone"] button{
    background:#0a7652!important;color:white!important;
}
section[data-testid="stSidebar"] div[data-baseweb="select"]>div{
    background:#075d43!important;color:white!important;border-color:#0c9b61!important;
}
.ca-safe-brand{
    display:flex;gap:.6rem;align-items:center;color:white;
    padding:.25rem 0 .7rem;margin-bottom:.25rem;
}
.ca-safe-brand .leaf{font-size:1.8rem;color:#54ef8a}
.ca-safe-brand b{font-size:1.05rem;letter-spacing:.02em}
.ca-safe-brand small{display:block;color:#dcefe3;font-size:.64rem;line-height:1.25;margin-top:.15rem}
</style>
""", unsafe_allow_html=True)


st.markdown("""
<style>
.ca-sidebar-info{
    margin:.35rem 0 .7rem;
    padding:.58rem .65rem;
    border-radius:8px;
    background:#07543e;
    border:1px solid rgba(87,235,144,.20);
    color:#effff4;
    font-size:.68rem;
    line-height:1.3;
}
.ca-side-divider{
    height:1px;
    background:rgba(255,255,255,.16);
    margin:.65rem 0 .55rem;
}
.ca-side-footer{
    display:flex;
    align-items:center;
    gap:.35rem;
    color:#86ee9e;
    font-size:.75rem;
    line-height:1.2;
    padding:.65rem .15rem .25rem;
}
section[data-testid="stSidebar"] [data-testid="stExpander"]{
    background:transparent!important;
    border-color:rgba(255,255,255,.12)!important;
}
</style>
""", unsafe_allow_html=True)

# ============================================================
# EcoFlux Brasil — V37
# Arquitetura:
# 1) Dados originais da torre CR3000: 1 min / 30 min / diário
# 2) Eddy Covariance / QC
# 3) Produtos processados: gap-filling, NEE, GPP, Reco, incertezas
# ============================================================

# -----------------------------
# Idioma
# -----------------------------
# O idioma pode ser alterado pelo menu superior (?lang=pt / ?lang=en).
# A leitura ocorre ANTES de definir PT para que toda a interface seja
# traduzida no mesmo rerun.
LANGUAGE = st.session_state.get("language_v29", "Português")
PT = LANGUAGE == "Português"

def tr(pt, en):
    return pt if PT else en

TABLE_MODE = st.session_state.get(
    "table_mode_v29",
    tr("Controles próprios", "Custom controls"),
)
CUSTOM_TABLES = TABLE_MODE == tr("Controles próprios", "Custom controls")

_TABLE_COUNTER = 0

def show_table(data, hide_index=True):
    global _TABLE_COUNTER
    _TABLE_COUNTER += 1
    key = f"table_v29_{_TABLE_COUNTER}"

    if not isinstance(data, pd.DataFrame):
        data = pd.DataFrame(data)

    if not CUSTOM_TABLES:
        st.dataframe(data, width="stretch", hide_index=hide_index)
        return

    view = data.copy()

    if len(view.columns):
        with st.expander(tr("Opções da tabela", "Table options"), expanded=False):
            c1, c2, c3 = st.columns([2, 1, 1])
            sort_col = c1.selectbox(
                tr("Ordenar por", "Sort by"),
                ["—"] + list(view.columns),
                key=f"{key}_sort",
            )
            direction = c2.selectbox(
                tr("Ordem", "Order"),
                [tr("Crescente", "Ascending"), tr("Decrescente", "Descending")],
                key=f"{key}_dir",
            )
            rows = c3.selectbox(
                tr("Linhas", "Rows"),
                [25, 50, 100, 250, tr("Todas", "All")],
                index=1,
                key=f"{key}_rows",
            )
            visible = st.multiselect(
                tr("Colunas visíveis", "Visible columns"),
                list(view.columns),
                default=list(view.columns),
                key=f"{key}_cols",
            )

        if visible:
            view = view[visible]
        if sort_col != "—" and sort_col in view.columns:
            asc = direction == tr("Crescente", "Ascending")
            try:
                view = view.sort_values(sort_col, ascending=asc, na_position="last")
            except Exception:
                pass
        if rows != tr("Todas", "All"):
            view = view.head(int(rows))

    st.markdown(
        """
        <style>
        .ecoflux-table {overflow-x:auto;border:1px solid rgba(128,128,128,.25);
                        border-radius:8px;margin-bottom:.8rem}
        .ecoflux-table table {border-collapse:collapse;width:100%;font-size:.93rem}
        .ecoflux-table th,.ecoflux-table td {padding:.45rem .65rem;
                        border-bottom:1px solid rgba(128,128,128,.18);
                        text-align:left;white-space:nowrap}
        .ecoflux-table th {font-weight:600;background:rgba(128,128,128,.08)}
        </style>
        """,
        unsafe_allow_html=True,
    )
    st.markdown(
        '<div class="ecoflux-table">' +
        view.to_html(index=not hide_index, escape=True, border=0) +
        "</div>",
        unsafe_allow_html=True,
    )

# -----------------------------
# Utilidades científicas
# -----------------------------
MISSING_SENTINELS = {-9999, -9999.0}
VARIABLE_PALETTE = [
    "#1f77b4", "#d62728", "#2ca02c", "#9467bd", "#ff7f0e",
    "#17becf", "#8c564b", "#e377c2", "#bcbd22", "#7f7f7f",
    "#393b79", "#637939", "#8c6d31", "#843c39", "#7b4173",
]

QC_CODE_COLORS = {
    0: "#1f77b4",
    1: "#ff7f0e",
    2: "#2ca02c",
    3: "#d62728",
    4: "#9467bd",
}

FOKEN_CLASS_COLORS = {
    "Alta qualidade": "#2ca02c",
    "Qualidade moderada": "#ff7f0e",
    "Baixa qualidade": "#d62728",
    "Fora da escala selecionada": "#7f7f7f",
}

TEMPORAL_FIELDS = {
    "timestamp", "date", "time", "datetime", "datatime",
    "record", "doy", "day_of_year", "year", "month", "day", "hour",
}

GAPFILL_FAMILIES = ["NEE", "LE", "H", "Rg", "VPD", "rH", "Tair", "Tsoil"]

SCIENTIFIC_GROUPS = {
    "Ventos e Turbulência": [
        "WS", "WindDir", "u", "v", "w", "ustar", "u*", "TKE", "sonic", "Tau"
    ],
    "Fluxos de Energia e Massa": [
        "H", "LE", "Fc", "co2_flux", "h2o_flux", "Tau", "NEE", "Reco", "GPP"
    ],
    "Balanço de Radiação": [
        "Rg_i", "Rg_r", "Rg", "SW_IN", "SW_OUT", "LW_IN", "LW_OUT", "NET",
        "Rn", "PAR", "PPFD"
    ],
    "Variáveis Bioclimáticas e de Solo": [
        "T_ar", "Tair", "AirTC", "UR_ar", "RH", "rH", "VPD", "PA", "P",
        "T_solo", "Tsoil", "VW_", "SWC", "VWC", "PPT", "G"
    ],
    "Diagnósticos e Controle de Qualidade": [
        "qc_", "_qc", "_fqc", "diag", "footprint"
    ],
}

def variable_color(var):
    idx = sum((i + 1) * ord(ch) for i, ch in enumerate(str(var))) % len(VARIABLE_PALETTE)
    return VARIABLE_PALETTE[idx]

def qc_color(code):
    try:
        return QC_CODE_COLORS.get(int(float(code)), "#7f7f7f")
    except Exception:
        return "#7f7f7f"

def is_qc(name):
    n = str(name).lower()
    return n.startswith("qc_") or "_qc" in n or "_fqc" in n or n.endswith("_qc")

def scientific_group(name):
    n = str(name)
    low = n.lower()
    if low in TEMPORAL_FIELDS:
        return "Temporal e Identificação"
    if is_qc(n):
        return "Diagnósticos e Controle de Qualidade"

    # ordem deliberada para evitar classificar GPP como G (solo)
    for group in [
        "Fluxos de Energia e Massa",
        "Balanço de Radiação",
        "Ventos e Turbulência",
        "Variáveis Bioclimáticas e de Solo",
        "Diagnósticos e Controle de Qualidade",
    ]:
        for token in SCIENTIFIC_GROUPS[group]:
            if token.lower() in low:
                return group
    return "Outras Variáveis / Produtos Derivados"

def clean_numeric(series):
    s = pd.to_numeric(series, errors="coerce")
    return s.mask(s.isin(MISSING_SENTINELS))

def unit_label(var, units):
    u = units.get(var, "")
    return f"{var} [{u}]" if str(u).strip() else str(var)

def unit_only(var, units):
    u = str(units.get(var, "")).strip()
    return u if u else tr("unidade não informada", "unit not reported")

def resolution_label(value):
    if PT:
        return value
    return {
        "1 min": "1 min",
        "30 min": "30 min",
        "Horário": "Hourly",
        "Diário": "Daily",
        "Semanal": "Weekly",
        "Mensal": "Monthly",
    }.get(value, value)

def temporal_hover_text(ts, resolution):
    ts = pd.Timestamp(ts)
    if resolution == "1 min":
        return ts.strftime("%d/%m/%Y %H:%M")
    if resolution == "30 min":
        return ts.strftime("%d/%m/%Y %H:%M")
    if resolution == "Horário":
        return ts.strftime("%d/%m/%Y %H:00")
    if resolution == "Diário":
        return ts.strftime("%d/%m/%Y")
    if resolution == "Semanal":
        end = ts.normalize()
        start = end - pd.Timedelta(days=6)
        return f"{start:%d/%m/%Y} – {end:%d/%m/%Y}"
    if resolution == "Mensal":
        months_pt = [
            "Janeiro","Fevereiro","Março","Abril","Maio","Junho",
            "Julho","Agosto","Setembro","Outubro","Novembro","Dezembro"
        ]
        months_en = [
            "January","February","March","April","May","June",
            "July","August","September","October","November","December"
        ]
        months = months_pt if PT else months_en
        return f"{months[ts.month-1]}/{ts.year}"
    return ts.strftime("%d/%m/%Y %H:%M")

def temporal_axis_title(resolution):
    return tr(
        {
            "1 min": "Data e hora",
            "30 min": "Data e hora",
            "Horário": "Data e hora",
            "Diário": "Data",
            "Semanal": "Período semanal",
            "Mensal": "Mês",
        }.get(resolution, "Data e hora"),
        {
            "1 min": "Date and time",
            "30 min": "Date and time",
            "Horário": "Date and time",
            "Diário": "Date",
            "Semanal": "Weekly period",
            "Mensal": "Month",
        }.get(resolution, "Date and time"),
    )

def period_controls(prefix, start, end):
    c1, c2, c3, c4 = st.columns(4)
    d1 = c1.date_input(tr("Data inicial", "Start date"), start.date(), key=f"{prefix}_d1")
    t1 = c2.time_input(tr("Hora inicial", "Start time"), start.time(), key=f"{prefix}_t1")
    d2 = c3.date_input(tr("Data final", "End date"), end.date(), key=f"{prefix}_d2")
    t2 = c4.time_input(tr("Hora final", "End time"), end.time(), key=f"{prefix}_t2")
    return pd.Timestamp.combine(d1, t1), pd.Timestamp.combine(d2, t2)

def filter_period(df, start, end):
    return df[(df["TIMESTAMP"] >= start) & (df["TIMESTAMP"] <= end)].copy()

def aggregate_numeric(df, vars_, resolution):
    d = df[["TIMESTAMP"] + vars_].copy().set_index("TIMESTAMP")
    if resolution in {"1 min", "30 min"}:
        return d.reset_index()
    rule = {
        "Horário": "1h",
        "Diário": "1D",
        "Semanal": "1W",
        "Mensal": "1MS",
    }[resolution]
    return d.resample(rule).mean(numeric_only=True).reset_index()

def expected_timedelta(source_key):
    return {
        "1 min": pd.Timedelta(minutes=1),
        "30 min": pd.Timedelta(minutes=30),
        "Diário": pd.Timedelta(days=1),
    }.get(source_key)

def gap_table(df, expected):
    if df is None or df.empty or expected is None:
        return pd.DataFrame()
    d = df[["TIMESTAMP"]].dropna().sort_values("TIMESTAMP").copy()
    d["diff"] = d["TIMESTAMP"].diff()
    gaps = d[d["diff"] > expected * 1.5].copy()
    rows = []
    for idx, row in gaps.iterrows():
        current = row["TIMESTAMP"]
        previous = d.loc[d.index[d.index.get_loc(idx)-1], "TIMESTAMP"]
        missing_est = max(int(round(row["diff"] / expected)) - 1, 0)
        rows.append({
            tr("Último registro antes da lacuna", "Last record before gap"): previous,
            tr("Primeiro registro após a lacuna", "First record after gap"): current,
            tr("Duração", "Duration"): str(row["diff"]),
            tr("Registros esperados ausentes", "Estimated missing records"): missing_est,
        })
    return pd.DataFrame(rows)

def add_gap_breaks(x, y, expected):
    if expected is None or len(x) == 0:
        return list(x), list(y)

    xs, ys = [], []
    prev = None
    for ts, val in zip(x, y):
        ts = pd.Timestamp(ts)
        if prev is not None and ts - prev > expected * 1.5:
            xs.append(prev + expected)
            ys.append(None)
        xs.append(ts)
        ys.append(None if pd.isna(val) else val)
        prev = ts
    return xs, ys

def line_plot(data, vars_, units, title, start, end, resolution, source_expected=None):
    fig = go.Figure()
    colors = {v: variable_color(v) for v in vars_}

    for v in vars_:
        values = pd.to_numeric(data[v], errors="coerce")
        x = data["TIMESTAMP"]

        if resolution in {"1 min", "30 min"} and source_expected is not None:
            pxs, pys = add_gap_breaks(x, values, source_expected)
            hover = [
                temporal_hover_text(ts, resolution) if ts is not None else ""
                for ts in pxs
            ]
            custom = np.column_stack([
                np.array(hover, dtype=object),
                np.array([unit_only(v, units)] * len(pxs), dtype=object),
            ])
            fig.add_trace(go.Scattergl(
                x=pxs, y=pys, mode="lines",
                name=unit_label(v, units),
                line=dict(color=colors[v], width=1.8),
                connectgaps=False,
                customdata=custom,
                hovertemplate=(
                    "<b>%{customdata[0]}</b><br>"
                    + str(v) + ": %{y:.6g} %{customdata[1]}<extra></extra>"
                ),
            ))
        else:
            hover = [temporal_hover_text(ts, resolution) for ts in x]
            custom = np.column_stack([
                np.array(hover, dtype=object),
                np.array([unit_only(v, units)] * len(data), dtype=object),
            ])
            fig.add_trace(go.Scattergl(
                x=x, y=values, mode="lines",
                name=unit_label(v, units),
                line=dict(color=colors[v], width=1.8),
                connectgaps=False,
                customdata=custom,
                hovertemplate=(
                    "<b>%{customdata[0]}</b><br>"
                    + str(v) + ": %{y:.6g} %{customdata[1]}<extra></extra>"
                ),
            ))

    fig.update_layout(
        title=title,
        xaxis_title=temporal_axis_title(resolution),
        yaxis_title=tr("Valor", "Value"),
        hovermode="x unified",
        height=480,
        margin=dict(l=20, r=20, t=55, b=20),
    )
    fig.update_xaxes(range=[start, end])
    st.plotly_chart(fig, width="stretch")

def stats_table(df, vars_, units):
    rows = []
    for v in vars_:
        s = pd.to_numeric(df[v], errors="coerce")
        rows.append({
            tr("Variável", "Variable"): v,
            tr("Unidade", "Unit"): unit_only(v, units),
            tr("N disponível", "N available"): int(s.notna().sum()),
            tr("Disponibilidade (%)", "Availability (%)"): round(100*s.notna().mean(), 2) if len(s) else np.nan,
            tr("Média", "Mean"): s.mean(),
            tr("Mediana", "Median"): s.median(),
            tr("Desvio-padrão", "Standard deviation"): s.std(),
            tr("Mínimo", "Minimum"): s.min(),
            tr("Máximo", "Maximum"): s.max(),
        })
    show_table(pd.DataFrame(rows))

def comparison_mode_label(value):
    if PT:
        return value
    return {
        "Gráficos separados": "Separate charts",
        "Mesmo gráfico — valores originais": "Same chart — original values",
        "Dois eixos Y": "Two Y axes",
        "Normalizado (z-score)": "Normalized (z-score)",
    }.get(value, value)

def plot_two_y_axes(data, vars_, units, start, end, resolution):
    fig = go.Figure()
    hover = [temporal_hover_text(ts, resolution) for ts in data["TIMESTAMP"]]
    for i, v in enumerate(vars_):
        fig.add_trace(go.Scattergl(
            x=data["TIMESTAMP"],
            y=data[v],
            mode="lines",
            name=unit_label(v, units),
            line=dict(color=variable_color(v), width=1.8),
            yaxis="y" if i % 2 == 0 else "y2",
            customdata=np.array(hover, dtype=object).reshape(-1, 1),
            hovertemplate=(
                "<b>%{customdata[0]}</b><br>" + str(v) +
                ": %{y:.6g} " + unit_only(v, units) + "<extra></extra>"
            ),
        ))
    left = [v for i, v in enumerate(vars_) if i % 2 == 0]
    right = [v for i, v in enumerate(vars_) if i % 2 == 1]
    fig.update_layout(
        title=tr("Comparação com dois eixos Y", "Comparison with two Y axes"),
        xaxis_title=temporal_axis_title(resolution),
        yaxis=dict(title=", ".join(left)),
        yaxis2=dict(title=", ".join(right), overlaying="y", side="right"),
        hovermode="x unified",
        height=500,
    )
    fig.update_xaxes(range=[start, end])
    st.plotly_chart(fig, width="stretch")

def plot_zscore(data, vars_, start, end, resolution):
    fig = go.Figure()
    hover = [temporal_hover_text(ts, resolution) for ts in data["TIMESTAMP"]]
    for v in vars_:
        s = pd.to_numeric(data[v], errors="coerce")
        sd = s.std()
        z = (s - s.mean()) / sd if pd.notna(sd) and sd != 0 else s*np.nan
        fig.add_trace(go.Scattergl(
            x=data["TIMESTAMP"], y=z, mode="lines",
            name=v,
            line=dict(color=variable_color(v), width=1.8),
            customdata=np.array(hover, dtype=object).reshape(-1, 1),
            hovertemplate="<b>%{customdata[0]}</b><br>"+str(v)+": %{y:.3f} z<extra></extra>",
        ))
    fig.update_layout(
        title=tr("Comparação normalizada (z-score)", "Normalized comparison (z-score)"),
        xaxis_title=temporal_axis_title(resolution),
        yaxis_title="z-score",
        hovermode="x unified",
        height=500,
    )
    fig.update_xaxes(range=[start, end])
    st.plotly_chart(fig, width="stretch")

# ============================================================
# Leitura Campbell TOA5 — modo econômico de memória
# ============================================================

def _uploaded_bytes(uploaded_file):
    if hasattr(uploaded_file, "getvalue"):
        return uploaded_file.getvalue()
    return uploaded_file.read()

def read_toa5_header(uploaded_file):
    uploaded_file.seek(0)
    header_lines = []
    for _ in range(4):
        raw = uploaded_file.readline()
        if not raw:
            break
        if isinstance(raw, bytes):
            raw = raw.decode("utf-8", errors="replace")
        header_lines.append(raw.rstrip("\r\n"))
    uploaded_file.seek(0)

    if len(header_lines) < 4:
        raise ValueError("Arquivo TOA5 incompleto.")

    meta = next(csv.reader([header_lines[0]]))
    headers = next(csv.reader([header_lines[1]]))
    units_row = next(csv.reader([header_lines[2]]))
    proc_row = next(csv.reader([header_lines[3]]))

    if not meta or meta[0] != "TOA5":
        raise ValueError("O arquivo não foi reconhecido como Campbell Scientific TOA5.")

    return meta, headers, units_row, proc_row

def classify_resolution_from_seconds(seconds):
    """
    Classifica a resolução a partir do intervalo temporal típico entre TIMESTAMPs.
    A classificação é baseada no conteúdo do arquivo, não no nome do arquivo.
    """
    if seconds is None or not np.isfinite(seconds) or seconds <= 0:
        return "Desconhecida"

    minutes = seconds / 60.0

    if 0.5 <= minutes <= 1.5:
        return "1 min"
    if 25 <= minutes <= 35:
        return "30 min"
    if 20 * 60 <= minutes <= 28 * 60:
        return "Diário"

    return "Desconhecida"

def identify_toa5_resolution(table_name, filename, interval_seconds=None):
    """
    Primeiro usa o intervalo temporal detectado no conteúdo.
    O nome do arquivo serve apenas como fallback.
    """
    detected = classify_resolution_from_seconds(interval_seconds)
    if detected != "Desconhecida":
        return detected

    text = f"{table_name} {filename}".lower()
    if "1min" in text or "1_min" in text:
        return "1 min"
    if "30min" in text or "30_min" in text:
        return "30 min"
    if "diario" in text or "diário" in text or "daily" in text:
        return "Diário"
    return "Desconhecida"

def toa5_file_key(uploaded_file):
    size = getattr(uploaded_file, "size", None)
    if size is None:
        pos = uploaded_file.tell()
        uploaded_file.seek(0, 2)
        size = uploaded_file.tell()
        uploaded_file.seek(pos)
    return f"{uploaded_file.name}|{size}"

def scan_toa5_summary(uploaded_file):
    """
    Lê somente TIMESTAMP para reconhecer automaticamente:
    - número de registros
    - início/fim
    - intervalo temporal típico
    - resolução 1 min / 30 min / diário

    A detecção usa o conteúdo temporal do arquivo e não depende do nome.
    """
    meta, headers, units_row, proc_row = read_toa5_header(uploaded_file)
    table_name = meta[-1] if meta else uploaded_file.name

    if "TIMESTAMP" not in headers:
        raise ValueError("Coluna TIMESTAMP não encontrada.")

    uploaded_file.seek(0)
    ts_df = pd.read_csv(
        uploaded_file,
        skiprows=4,
        names=headers,
        usecols=["TIMESTAMP"],
        low_memory=True,
    )
    uploaded_file.seek(0)

    ts = pd.to_datetime(ts_df["TIMESTAMP"], errors="coerce").dropna().sort_values()
    del ts_df

    n = int(len(ts))
    first_ts = ts.iloc[0] if n else None
    last_ts = ts.iloc[-1] if n else None

    typical_seconds = None
    median_seconds = None

    if n >= 2:
        diffs = ts.diff().dropna().dt.total_seconds()
        diffs = diffs[diffs > 0]

        if not diffs.empty:
            median_seconds = float(diffs.median())

            # O intervalo modal é mais robusto que a mediana quando há uma lacuna
            # real longa na série.
            rounded = diffs.round().astype("int64")
            modes = rounded.mode()
            if not modes.empty:
                typical_seconds = float(modes.iloc[0])
            else:
                typical_seconds = median_seconds

    res = identify_toa5_resolution(
        table_name,
        uploaded_file.name,
        interval_seconds=typical_seconds if typical_seconds is not None else median_seconds,
    )

    return {
        "resolution": res,
        "table_name": table_name,
        "filename": uploaded_file.name,
        "records": n,
        "start": first_ts,
        "end": last_ts,
        "interval_seconds": typical_seconds,
        "median_interval_seconds": median_seconds,
        "headers": headers,
        "units": {
            h: str(u).strip()
            for h, u in zip(headers, units_row)
            if str(u).strip()
        },
        "processing": {
            h: str(p).strip()
            for h, p in zip(headers, proc_row)
            if str(p).strip()
        },
        "meta": meta,
    }

def parse_toa5_stream(uploaded_file):
    """
    Faz o pandas ler diretamente do UploadedFile, evitando:
    bytes -> string gigante -> splitlines -> StringIO.
    Isso reduz bastante o pico de memória dos arquivos de 1 minuto.
    """
    meta, headers, units_row, proc_row = read_toa5_header(uploaded_file)
    table_name = meta[-1] if meta else uploaded_file.name

    uploaded_file.seek(0)
    df = pd.read_csv(
        uploaded_file,
        skiprows=4,
        names=headers,
        na_values=["NAN", "NaN", "-9999"],
        low_memory=True,
    )
    uploaded_file.seek(0)

    if "TIMESTAMP" not in df.columns:
        raise ValueError("Coluna TIMESTAMP não encontrada.")

    df["TIMESTAMP"] = pd.to_datetime(df["TIMESTAMP"], errors="coerce")
    df = df[df["TIMESTAMP"].notna()].sort_values("TIMESTAMP").reset_index(drop=True)

    for c in df.columns:
        if c == "TIMESTAMP":
            continue
        if c.endswith("_TMx") or c.endswith("_TMn"):
            continue

        if not pd.api.types.is_numeric_dtype(df[c]):
            numeric = pd.to_numeric(df[c], errors="coerce")
            if numeric.notna().sum() > 0:
                df[c] = numeric

        if pd.api.types.is_numeric_dtype(df[c]):
            df[c] = df[c].mask(df[c].isin(MISSING_SENTINELS))

    units = {
        h: str(u).strip()
        for h, u in zip(headers, units_row)
        if str(u).strip()
    }
    processing = {
        h: str(p).strip()
        for h, p in zip(headers, proc_row)
        if str(p).strip()
    }

    return {
        "df": df,
        "units": units,
        "processing": processing,
        "meta": meta,
        "table_name": table_name,
        "filename": uploaded_file.name,
    }

# ============================================================
# Leitura XLSX processado
# ============================================================

@st.cache_data(show_spinner=False)
def load_processed_xlsx(file_bytes):
    bio = io.BytesIO(file_bytes)
    xls = pd.ExcelFile(bio)
    sheet = "output" if "output" in xls.sheet_names else xls.sheet_names[0]

    bio.seek(0)
    meta = pd.read_excel(bio, sheet_name=sheet, header=None, nrows=2)
    headers = [str(x).strip() for x in meta.iloc[0].tolist()]
    raw_units = meta.iloc[1].tolist()
    units = {
        h: str(u).strip()
        for h, u in zip(headers, raw_units)
        if pd.notna(u) and str(u).strip() not in {"", "-", "nan"}
    }

    bio.seek(0)
    df = pd.read_excel(bio, sheet_name=sheet, header=0, skiprows=[1]).copy()

    time_candidates = [
        c for c in df.columns
        if str(c).strip().lower() in {"date time","datetime","date_time","datatime","timestamp"}
    ]
    if not time_candidates:
        raise ValueError("Coluna temporal não encontrada na planilha processada.")

    tc = time_candidates[0]
    df["TIMESTAMP"] = pd.to_datetime(df[tc], errors="coerce")
    df = df[df["TIMESTAMP"].notna()].sort_values("TIMESTAMP").reset_index(drop=True)

    for c in df.columns:
        if c in {tc, "TIMESTAMP"}:
            continue
        num = pd.to_numeric(df[c], errors="coerce")
        if num.notna().sum() > 0:
            df[c] = num.mask(num.isin(MISSING_SENTINELS))

    return df, units, sheet

# ============================================================
# Cabeçalho principal + uploads
# ============================================================

# Rotas são definidas antes da leitura dos arquivos para que a interface exista
# mesmo sem upload.
pages = {
    "overview": tr("Visão Geral", "Overview"),
    "tower": tr("Dados Originais da Torre", "Original Tower Data"),
    "structure": tr("Estrutura Científica", "Scientific Structure"),
    "compare": tr("Comparar Variáveis", "Compare Variables"),
    "gapfill": tr("Preenchimento de Lacunas", "Gap Filling"),
    "carbon": tr("Balanço de Carbono", "Carbon Balance"),
    "qc": tr("Qualidade dos Dados", "Data Quality"),
    "about": tr("Sobre os Dados", "About the Data"),
    "request": tr("Solicitar Dados", "Request Data"),
}
_inicio_label = tr("Início", "Home")

if "_ca_route" not in st.session_state:
    st.session_state["_ca_route"] = "inicio"
if "_ca_history" not in st.session_state:
    st.session_state["_ca_history"] = []

def _go(route):
    current = st.session_state.get("_ca_route", "inicio")
    if route != current:
        st.session_state["_ca_history"].append(current)
        st.session_state["_ca_route"] = route

def _back():
    hist = st.session_state.get("_ca_history", [])
    if hist:
        st.session_state["_ca_route"] = hist.pop()




# Cabeçalho/navegação nativos do Streamlit: mesma sessão, sem href/query params.
if "_ca_route" not in st.session_state: st.session_state["_ca_route"]="inicio"
if "_ca_history" not in st.session_state: st.session_state["_ca_history"]=[]

def _go(r):
    cur=st.session_state["_ca_route"]
    if r!=cur:
        st.session_state["_ca_history"].append(cur)
        st.session_state["_ca_route"]=r

def _back():
    if st.session_state["_ca_history"]:
        st.session_state["_ca_route"]=st.session_state["_ca_history"].pop()

st.markdown("""
<style>
section[data-testid="stSidebar"],[data-testid="collapsedControl"]{display:none!important}
header[data-testid="stHeader"]{height:0!important;min-height:0!important;background:transparent!important}
[data-testid="stToolbar"],[data-testid="stDecoration"]{display:none!important}
[data-testid="stMainBlockContainer"],.main .block-container{
 max-width:100%!important;width:100%!important;padding:0!important;margin:0!important
}
[data-testid="stMainBlockContainer"]>div{gap:0!important}
.header-anchor{display:none!important}
div[data-testid="stHorizontalBlock"]:has(.header-anchor){
 width:100%!important;height:105px!important;min-height:105px!important;margin:0!important;padding:0 38px!important;
 background:linear-gradient(90deg,#005a43 0%,#00684b 48%,#004c39 100%)!important;
 gap:8px!important;align-items:center!important
}
.ca-brand-inline{color:white;line-height:1.05;padding-right:10px}
.ca-brand-inline b{font-size:28px;font-weight:800;white-space:nowrap;letter-spacing:-.2px}
.ca-brand-inline small{display:block;font-size:13px;line-height:1.25;margin-top:6px;color:#effff4}
div[data-testid="stHorizontalBlock"]:has(.header-anchor) button,
div[data-testid="stHorizontalBlock"]:has(.header-anchor) [data-testid="stPopover"]>button{
 min-height:58px!important;border:0!important;border-radius:10px!important;
 background:transparent!important;color:#fff!important;font-size:17px!important;letter-spacing:-.1px!important;line-height:1!important;
 font-weight:650!important;white-space:nowrap!important;box-shadow:none!important;padding:.35rem .55rem!important
}
div[data-testid="stHorizontalBlock"]:has(.header-anchor) button:hover,
div[data-testid="stHorizontalBlock"]:has(.header-anchor) button[kind="primary"]{
 background:#16ad63!important;color:#fff!important
}
div[data-testid="stHorizontalBlock"]:has(.header-anchor)>div:nth-last-child(3) button{
 border:1px solid #23c978!important
}
div[data-testid="stPopoverBody"]{
 background:#fff!important;color:#26352f!important;border-radius:9px!important;
 border:1px solid rgba(0,0,0,.08)!important;box-shadow:0 12px 30px rgba(0,0,0,.25)!important;
 min-width:275px!important;z-index:99999!important
}
div[data-testid="stPopoverBody"]>div,
div[data-testid="stPopoverBody"] div[data-testid="stVerticalBlock"]{background:#fff!important}
div[data-testid="stPopoverBody"] button{
 width:100%!important;justify-content:flex-start!important;background:#fff!important;
 color:#26352f!important;border:0!important;border-radius:6px!important
}
div[data-testid="stPopoverBody"] button:hover{background:#eaf8ef!important;color:#07533f!important}
div[data-testid="stPopoverBody"] label,div[data-testid="stPopoverBody"] p,
div[data-testid="stPopoverBody"] span{color:#26352f!important}
div[data-testid="stPopoverBody"] [data-testid="stFileUploader"]{min-width:430px!important}
div[data-testid="stPopoverBody"] [data-testid="stFileUploaderDropzone"]{
 background:#f5faf7!important;border-color:#9bc9ad!important
}
.ca-home-frame{
 width:100vw!important;height:calc(100vh - 105px)!important;overflow:hidden!important;
 margin:0!important;padding:0!important;background:#073d2d!important
}
.ca-home-image{
 display:block!important;width:100vw!important;max-width:none!important;
 height:calc((100vh - 105px) * 1.136)!important;
 object-fit:fill!important;
 margin-top:calc((100vh - 105px) * -0.136)!important;padding:0!important
}
div[data-testid="stElementContainer"]:has(.ca-home-image),
div[data-testid="stMarkdownContainer"]:has(.ca-home-image){margin:0!important;padding:0!important}
</style>
""", unsafe_allow_html=True)


active=st.session_state["_ca_route"]
hdr=st.columns([3.25,.82,1.06,.94,1.04,1.05,1.20,1.05,.92,1.18],gap="small")
with hdr[0]:
 st.markdown('''<span class="header-anchor"></span><div class="ca-brand-inline">
<div class="ca-brand-logo ca-brand-logo-real"><img src="data:image/png;base64,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" alt="Símbolo Carbono em Ação"></div>
<div class="ca-brand-copy"><b>CARBONO EM AÇÃO</b><small>Plataforma Inteligente de Monitoramento<br>de Carbono e Micrometeorologia</small></div></div>''',unsafe_allow_html=True)
with hdr[1]:
 if st.button(tr("Início","Home"),key="n_home",use_container_width=True,type="primary" if active=="inicio" else "secondary"): _go("inicio");st.rerun()
with hdr[2]:
 if st.button(tr("Visão Geral","Overview"),key="n_over",use_container_width=True,type="primary" if active=="overview" else "secondary"): _go("overview");st.rerun()
with hdr[3]:
 with st.popover(tr("Dados","Data"),use_container_width=True):
  if st.button(pages["tower"],key="n_tower",use_container_width=True): _go("tower");st.rerun()
  if st.button(pages["structure"],key="n_struct",use_container_width=True): _go("structure");st.rerun()
with hdr[4]:
 with st.popover(tr("Análises","Analyses"),use_container_width=True):
  if st.button(pages["compare"],key="n_comp",use_container_width=True): _go("compare");st.rerun()
  if st.button(pages["gapfill"],key="n_gap",use_container_width=True): _go("gapfill");st.rerun()
  if st.button(pages["carbon"],key="n_carbon",use_container_width=True): _go("carbon");st.rerun()
with hdr[5]:
 with st.popover(tr("Qualidade","Quality"),use_container_width=True):
  if st.button(pages["qc"],key="n_qc",use_container_width=True): _go("qc");st.rerun()
with hdr[6]:
 with st.popover(tr("Informações","Information"),use_container_width=True):
  if st.button(pages["about"],key="n_about",use_container_width=True): _go("about");st.rerun()
  if st.button(pages["request"],key="n_req",use_container_width=True): _go("request");st.rerun()
with hdr[7]:
 with st.popover(tr("Arquivos","Files"),use_container_width=True):
  tower_files=st.file_uploader(tr("Dados originais CR3000 (.dat)","Original CR3000 data (.dat)"),type=["dat"],accept_multiple_files=True,key="tower_dat_v34")
  processed_file=st.file_uploader(tr("Produtos processados (.xlsx) — opcional","Processed products (.xlsx) — optional"),type=["xlsx"],key="processed_xlsx_v34")
with hdr[8]:
 with st.popover(tr("Idioma","Language"),use_container_width=True):
  if st.button("Português",key="l_pt",use_container_width=True):
   st.session_state["language_v29"]="Português";st.rerun()
  if st.button("English",key="l_en",use_container_width=True):
   st.session_state["language_v29"]="English";st.rerun()
with hdr[9]:
 with st.popover(tr("Preferências","Preferences"),use_container_width=True):
  st.caption(tr("Opções da interface","Interface options"))

tower_files=tower_files or []
if "_ecoflux_parsed_toa5" not in st.session_state:
    st.session_state["_ecoflux_parsed_toa5"] = {}

if "_ecoflux_toa5_summary" not in st.session_state:
    st.session_state["_ecoflux_toa5_summary"] = {}

parsed_cache = st.session_state["_ecoflux_parsed_toa5"]
summary_cache = st.session_state["_ecoflux_toa5_summary"]

tower_file_map = {}
tower_summaries = {}

active_keys = set()

for f in tower_files or []:
    try:
        key = toa5_file_key(f)
        active_keys.add(key)

        if key not in summary_cache:
            summary_cache[key] = scan_toa5_summary(f)

        summary = summary_cache[key]
        res = summary["resolution"]

        if res == "Desconhecida":
            st.warning(
                tr(
                    f"{f.name}: resolução temporal não reconhecida automaticamente.",
                    f"{f.name}: temporal resolution could not be recognized automatically.",
                )
            )
            continue

        if res in tower_file_map:
            st.warning(
                tr(
                    f"Há mais de um arquivo reconhecido como {res}. O último selecionado será usado.",
                    f"More than one file was recognized as {res}. The last selected file will be used.",
                )
            )

        tower_file_map[res] = f
        tower_summaries[res] = summary

        # 30 min e diário são pequenos e úteis em várias páginas.
        # O arquivo de 1 min fica sob demanda.
        if res != "1 min" and key not in parsed_cache:
            parsed_cache[key] = parse_toa5_stream(f)

    except Exception as exc:
        st.error(f"{getattr(f, 'name', 'arquivo')}: {exc}")


# O reconhecimento temporal continua sendo executado normalmente.
# Os avisos de sucesso foram retirados apenas da interface lateral para
# manter a navegação sempre visível, sem alterar a lógica científica.

# Remove referências de arquivos que não estão mais selecionados.
for old_key in list(parsed_cache.keys()):
    if old_key not in active_keys:
        del parsed_cache[old_key]
for old_key in list(summary_cache.keys()):
    if old_key not in active_keys:
        del summary_cache[old_key]

def get_tower_source(resolution, load_if_needed=True):
    f = tower_file_map.get(resolution)
    if f is None:
        return None

    key = toa5_file_key(f)

    if key not in parsed_cache and load_if_needed:
        with st.spinner(tr(
            f"Carregando dados CR3000 de {resolution}...",
            f"Loading {resolution} CR3000 data...",
        )):
            parsed_cache[key] = parse_toa5_stream(f)

    return parsed_cache.get(key)

# Fontes já carregadas (30 min, diário e 1 min caso tenha sido solicitado antes).
tower_sources = {}
for res, f in tower_file_map.items():
    key = toa5_file_key(f)
    if key in parsed_cache:
        tower_sources[res] = parsed_cache[key]

processed = None
if processed_file is not None:
    try:
        pdf, punits, psheet = load_processed_xlsx(_uploaded_bytes(processed_file))
        processed = {"df": pdf, "units": punits, "sheet": psheet}
    except Exception as exc:
        st.error(tr(
            f"Erro no XLSX processado: {exc}",
            f"Processed XLSX error: {exc}",
        ))

# A interface e a navegação devem existir mesmo antes de qualquer upload.
# Sem dados, as páginas científicas continuam acessíveis e exibem seus próprios
# avisos de que a fonte correspondente ainda não foi carregada.
_no_data_yet = not tower_file_map and processed is None
_unrecognized_upload = bool(tower_files) and not tower_file_map

# ============================================================
# Rota ativa
# ============================================================
_no_data_yet = not tower_file_map and processed is None
_unrecognized_upload = bool(tower_files) and not tower_file_map

_route=st.session_state.get("_ca_route","inicio")
if _route not in {"inicio",*pages.keys()}:
    _route="inicio";st.session_state["_ca_route"]="inicio"
page=_inicio_label if _route=="inicio" else pages[_route]

if _route != "inicio" and _no_data_yet:
    if _unrecognized_upload:
        st.error(tr(
            "Os arquivos foram enviados, mas nenhuma resolução temporal pôde ser reconhecida. Verifique se são arquivos Campbell TOA5 com uma coluna TIMESTAMP válida.",
            "Files were uploaded, but no temporal resolution could be recognized. Check that they are Campbell TOA5 files with a valid TIMESTAMP column.",
        ))
    else:
        st.info(tr(
            "A interface está disponível. Para executar as análises científicas, use Arquivos no cabeçalho para carregar os dados CR3000 e, quando necessário, a planilha processada.",
            "The interface is available. To run scientific analyses, use Files in the header to upload CR3000 data and, when needed, the processed workbook.",
        ))

if page == _inicio_label:
    _home_img = Path(__file__).with_name("carbono_em_acao_home_aprovada.png")
    if _home_img.exists():
        st.markdown(
            f'<div class="ca-home-frame"><img class="ca-home-image" src="data:image/png;base64,{base64.b64encode(_home_img.read_bytes()).decode("ascii")}" /></div>',
            unsafe_allow_html=True,
        )
    else:
        st.warning(tr(
            "Arquivo carbono_em_acao_home_aprovada.png não encontrado.",
            "File carbono_em_acao_home_aprovada.png not found."
        ))
    st.stop()

# Espaçamento somente do conteúdo científico.
st.markdown("""
<style>
.ca-science-pad{height:1px}
[data-testid="stMainBlockContainer"]{padding-left:1.5rem!important;padding-right:1.5rem!important;padding-bottom:2rem!important}

</style>
<div class="ca-science-pad"></div>
""", unsafe_allow_html=True)

# Daqui para baixo, a lógica científica é exatamente a original:
# Visão Geral continua sendo Visão Geral, não a imagem de abertura.
page_key = next(k for k, v in pages.items() if v == page)




# ============================================================
# Visão Geral
# ============================================================

if page_key == "overview":
    st.markdown('<div class="ecoflux-hero">CARBONO EM AÇÃO</div>', unsafe_allow_html=True)

    recognized_count = len(tower_summaries)
    processed_count = 1 if processed_file is not None else 0
    total_loaded = recognized_count + processed_count
    if total_loaded:
        st.markdown(
            '<div class="ecoflux-success">'
            '<div class="ecoflux-success-line">✅ ' +
            tr(
                f"{total_loaded} arquivo(s) carregado(s): {recognized_count} CR3000" + (" + 1 XLSX processado" if processed_count else ""),
                f"{total_loaded} file(s) loaded: {recognized_count} CR3000" + (" + 1 processed XLSX" if processed_count else ""),
            ) +
            '</div>'
            '<div class="ecoflux-success-sub">' +
            tr(
                "Navegue pelas análises usando o menu superior ou pelas opções abaixo.",
                "Navigate analyses using the top menu or the options below.",
            ) +
            '</div></div>',
            unsafe_allow_html=True,
        )

    st.markdown(
        '<div class="ecoflux-section-title">' +
        tr("Resumo dos arquivos carregados", "Loaded files summary") +
        '</div>',
        unsafe_allow_html=True,
    )

    summary_rows = []
    for res in ["1 min", "30 min", "Diário"]:
        if res in tower_summaries:
            sm = tower_summaries[res]
            period = "—"
            if sm["start"] is not None and sm["end"] is not None:
                if res == "Diário":
                    period = f"{sm['start']:%d/%m/%Y} → {sm['end']:%d/%m/%Y}"
                else:
                    period = f"{sm['start']:%d/%m/%Y %H:%M} → {sm['end']:%d/%m/%Y %H:%M}"

            display_res = tr(
                "Diário (24h)" if res == "Diário" else res,
                "Daily (24h)" if res == "Diário" else res,
            )

            summary_rows.append(
                "<tr>"
                f"<td><span class='resolution-pill'>{display_res}</span></td>"
                f"<td>{sm['filename']}</td>"
                f"<td>{sm['records']:,}</td>"
                f"<td>{period}</td>"
                f"<td>{sm['interval_seconds']:.1f} s</td>"
                "<td><span class='ok-status'>● OK</span></td>"
                "</tr>"
            )

    # O XLSX aparece no resumo sempre que foi selecionado.
    if processed_file is not None:
        _pname = getattr(processed_file, "name", "XLSX")
        if processed is not None:
            _pdf = processed["df"]
            _pstart = _pdf["TIMESTAMP"].min() if "TIMESTAMP" in _pdf.columns and not _pdf.empty else None
            _pend = _pdf["TIMESTAMP"].max() if "TIMESTAMP" in _pdf.columns and not _pdf.empty else None
            _pperiod = "—"
            if pd.notna(_pstart) and pd.notna(_pend):
                _pperiod = f"{_pstart:%d/%m/%Y %H:%M} → {_pend:%d/%m/%Y %H:%M}"
            _precords = f"{len(_pdf):,}"
            _pstatus = "<span class='ok-status'>● OK</span>"
        else:
            _pperiod, _precords = "—", "—"
            _pstatus = "<span style='color:#b7791f;font-weight:700'>● XLSX selecionado</span>"
        summary_rows.append(
            "<tr>"
            f"<td><span class='resolution-pill'>{tr('Processado XLSX','Processed XLSX')}</span></td>"
            f"<td>{_pname}</td><td>{_precords}</td><td>{_pperiod}</td><td>—</td>"
            f"<td>{_pstatus}</td></tr>"
        )

    summary_html = (
        "<div class='ecoflux-summary-wrap'>"
        "<table class='ecoflux-summary'>"
        "<thead><tr>"
        f"<th>{tr('Resolução reconhecida','Recognized resolution')}</th>"
        f"<th>{tr('Arquivo','File')}</th>"
        f"<th>{tr('Registros','Records')}</th>"
        f"<th>{tr('Período detectado','Detected period')}</th>"
        f"<th>{tr('Δ tempo mediano','Median Δt')}</th>"
        f"<th>{tr('Status','Status')}</th>"
        "</tr></thead><tbody>"
        + "".join(summary_rows) +
        "</tbody></table></div>"
    )
    st.markdown(summary_html, unsafe_allow_html=True)
    if processed_file is not None:
        if processed is not None:
            st.success(tr(
                f"XLSX reconhecido: {processed_file.name} — {len(processed['df']):,} registros.",
                f"XLSX recognized: {processed_file.name} — {len(processed['df']):,} records."
            ))
        else:
            st.warning(tr(
                f"XLSX selecionado: {processed_file.name}. A leitura processada precisa ser verificada.",
                f"XLSX selected: {processed_file.name}. Processed-data reading needs verification."
            ))

    st.markdown(
        '<div class="ecoflux-info">ℹ️ ' +
        tr(
            "A identificação da resolução foi feita automaticamente com base no intervalo de tempo entre os registros (TIMESTAMP).",
            "Resolution was identified automatically from the interval between TIMESTAMP records.",
        ) +
        '</div>',
        unsafe_allow_html=True,
    )

    st.markdown(
        '<div class="ecoflux-section-title">' +
        tr("O que você deseja fazer?", "What would you like to do?") +
        '</div>',
        unsafe_allow_html=True,
    )

    icon_1min = """
    <svg width="34" height="34" viewBox="0 0 24 24" fill="none">
      <path d="M3 19V5M3 19H21" stroke="#2F6FED" stroke-width="1.8" stroke-linecap="round"/>
      <path d="M6 15L10 11L13 13L19 7" stroke="#2F6FED" stroke-width="1.8"
            stroke-linecap="round" stroke-linejoin="round"/>
    </svg>
    """
    icon_30 = """
    <svg width="34" height="34" viewBox="0 0 24 24" fill="none">
      <circle cx="12" cy="12" r="8" stroke="#F39C12" stroke-width="1.8"/>
      <path d="M12 7V12L15.5 14" stroke="#F39C12" stroke-width="1.8"
            stroke-linecap="round" stroke-linejoin="round"/>
    </svg>
    """
    icon_daily = """
    <svg width="34" height="34" viewBox="0 0 24 24" fill="none">
      <rect x="4" y="5" width="16" height="15" rx="2" stroke="#2E9D57" stroke-width="1.8"/>
      <path d="M8 3V7M16 3V7M4 9H20" stroke="#2E9D57" stroke-width="1.8" stroke-linecap="round"/>
    </svg>
    """
    icon_xlsx = """
    <svg width="34" height="34" viewBox="0 0 24 24" fill="none">
      <rect x="4" y="5" width="16" height="14" rx="2" stroke="#7D3FB2" stroke-width="1.8"/>
      <path d="M4 10H20M9 10V19M15 10V19" stroke="#7D3FB2" stroke-width="1.5"/>
    </svg>
    """

    actions_html = (
        "<div class='ecoflux-actions'>"
        "<div class='ecoflux-action-card'>"
        f"<div class='ecoflux-action-icon'>{icon_1min}</div>"
        "<div class='ecoflux-action-text'><h4>" +
        tr("Análise 1 min", "1-min analysis") +
        "</h4><p>" +
        tr("Fluxos, meteorologia e análises detalhadas", "Fluxes, meteorology and detailed analyses") +
        "</p></div></div>"

        "<div class='ecoflux-action-card'>"
        f"<div class='ecoflux-action-icon'>{icon_30}</div>"
        "<div class='ecoflux-action-text'><h4>" +
        tr("Análise 30 min", "30-min analysis") +
        "</h4><p>" +
        tr("Médias e estatísticas semi-horárias", "Half-hourly means and statistics") +
        "</p></div></div>"

        "<div class='ecoflux-action-card'>"
        f"<div class='ecoflux-action-icon'>{icon_daily}</div>"
        "<div class='ecoflux-action-text'><h4>" +
        tr("Análise diária", "Daily analysis") +
        "</h4><p>" +
        tr("Médias e estatísticas diárias", "Daily means and statistics") +
        "</p></div></div>"

        "<div class='ecoflux-action-card'>"
        f"<div class='ecoflux-action-icon'>{icon_xlsx}</div>"
        "<div class='ecoflux-action-text'><h4>" +
        tr("Produtos processados", "Processed products") +
        "</h4><p>" +
        tr("Visualizar produtos da planilha XLSX", "View products from the XLSX workbook") +
        "</p></div></div>"
        "</div>"
    )
    st.markdown(actions_html, unsafe_allow_html=True)

    st.markdown(
        '<div class="ecoflux-tip">💡 ' +
        tr(
            "Dica: você pode carregar ou substituir os arquivos a qualquer momento. "
            "A classificação será refeita automaticamente.",
            "Tip: you can upload or replace the files at any time. "
            "Classification will run again automatically.",
        ) +
        '</div>',
        unsafe_allow_html=True,
    )

    if "30 min" in tower_file_map:
        src30 = get_tower_source("30 min", load_if_needed=True)
        if src30 is not None:
            gaps = gap_table(src30["df"], expected_timedelta("30 min"))
            if not gaps.empty:
                st.markdown(
                    '<div class="ecoflux-section-title">' +
                    tr(
                        "Continuidade temporal — série de 30 minutos",
                        "Temporal continuity — 30-minute series",
                    ) +
                    '</div>',
                    unsafe_allow_html=True,
                )
                st.markdown(
                    '<div class="ecoflux-gap-warning">⚠️ ' +
                    tr(
                        f"Foram detectadas {len(gaps)} lacuna(s) real(is) na aquisição. "
                        "Os gráficos não conectam linhas através desses intervalos.",
                        f"{len(gaps)} real acquisition gap(s) were detected. "
                        "Plots do not connect lines across those intervals.",
                    ) +
                    '</div>',
                    unsafe_allow_html=True,
                )
                show_table(gaps)

elif page_key == "tower":
    st.header(tr("Dados Originais da Torre", "Original Tower Data"))

    source_order = [x for x in ["1 min", "30 min", "Diário"] if x in tower_file_map]
    if not source_order:
        st.info(tr("Nenhum arquivo CR3000 carregado.", "No CR3000 file loaded."))
        st.stop()

    source = st.selectbox(
        tr("Resolução observacional", "Observational resolution"),
        source_order,
        format_func=resolution_label,
        key="tower_source_v34",
    )

    src = get_tower_source(source, load_if_needed=True)
    if src is None:
        st.error(tr("Não foi possível carregar esta fonte.", "Unable to load this source."))
        st.stop()
    df = src["df"]
    units = src["units"]
    expected = expected_timedelta(source)

    numeric_vars = [
        c for c in df.columns
        if c not in {"TIMESTAMP", "RECORD"} and pd.api.types.is_numeric_dtype(df[c])
    ]
    groups = {}
    for c in numeric_vars:
        groups.setdefault(scientific_group(c), []).append(c)

    group = st.selectbox(
        tr("Grupo científico", "Scientific group"),
        list(groups.keys()),
        key="tower_group_v29",
    )
    var = st.selectbox(
        tr("Variável", "Variable"),
        groups[group],
        format_func=lambda x: unit_label(x, units),
        key="tower_var_v29",
    )

    full_start = df["TIMESTAMP"].min()
    full_end = df["TIMESTAMP"].max()
    start, end = period_controls("tower_v29", full_start, full_end)

    resolution_options = {
        "1 min": ["1 min", "30 min", "Horário", "Diário", "Semanal", "Mensal"],
        "30 min": ["30 min", "Horário", "Diário", "Semanal", "Mensal"],
        "Diário": ["Diário", "Semanal", "Mensal"],
    }[source]

    agg_res = st.selectbox(
        tr("Resolução do gráfico", "Plot resolution"),
        resolution_options,
        format_func=resolution_label,
        key="tower_plot_res_v29",
    )

    if start > end:
        st.error(tr("Período inválido.", "Invalid period."))
    else:
        sub = filter_period(df, start, end)
        data = aggregate_numeric(sub, [var], agg_res)
        line_plot(
            data, [var], units,
            unit_label(var, units),
            start, end, agg_res,
            source_expected=expected if agg_res in {"1 min","30 min"} else None,
        )
        stats_table(sub, [var], units)

        gaps = gap_table(sub, expected)
        if not gaps.empty:
            st.subheader(tr("Lacunas no período selecionado", "Gaps in selected period"))
            show_table(gaps)

# ============================================================
# Estrutura Científica
# ============================================================

elif page_key == "structure":
    st.header(tr("Estrutura Científica", "Scientific Structure"))
    st.write(tr(
        "As variáveis são organizadas segundo a estrutura típica de uma torre micrometeorológica. "
        "As unidades exibidas vêm dos próprios arquivos TOA5 ou da planilha processada.",
        "Variables are organized according to a typical micrometeorological tower structure. "
        "Displayed units come from the TOA5 files or the processed workbook.",
    ))

    rows = []
    include_1min_structure = st.checkbox(
        tr(
            "Incluir estrutura detalhada do arquivo de 1 min",
            "Include detailed structure of the 1-min file",
        ),
        value=False,
        key="structure_1min_v34",
        help=tr(
            "Deixe desmarcado para economizar memória. O cabeçalho de 1 min continua reconhecido na Visão Geral.",
            "Leave unchecked to save memory. The 1-min header remains recognized in Overview.",
        ),
    )

    structure_sources = {}
    for res in ["30 min", "Diário"]:
        if res in tower_file_map:
            src_tmp = get_tower_source(res, load_if_needed=True)
            if src_tmp is not None:
                structure_sources[res] = src_tmp

    if include_1min_structure and "1 min" in tower_file_map:
        src_tmp = get_tower_source("1 min", load_if_needed=True)
        if src_tmp is not None:
            structure_sources["1 min"] = src_tmp

    for res, src in structure_sources.items():
        df = src["df"]
        for c in df.columns:
            if c == "TIMESTAMP":
                continue
            rows.append({
                tr("Fonte", "Source"): src["table_name"],
                tr("Resolução", "Resolution"): resolution_label(res),
                tr("Grupo", "Group"): scientific_group(c),
                tr("Variável", "Variable"): c,
                tr("Unidade", "Unit"): src["units"].get(c, ""),
                tr("Processamento Campbell", "Campbell processing"): src["processing"].get(c, ""),
            })

    if processed is not None:
        for c in processed["df"].columns:
            if c == "TIMESTAMP":
                continue
            rows.append({
                tr("Fonte", "Source"): tr("Produtos processados", "Processed products"),
                tr("Resolução", "Resolution"): "30 min / produtos",
                tr("Grupo", "Group"): scientific_group(c),
                tr("Variável", "Variable"): c,
                tr("Unidade", "Unit"): processed["units"].get(c, ""),
                tr("Processamento Campbell", "Campbell processing"): "",
            })

    show_table(pd.DataFrame(rows))

# ============================================================
# Comparar Variáveis
# ============================================================

elif page_key == "compare":
    st.header(tr("Comparar Variáveis", "Compare Variables"))

    source_choices = [resolution_label(x) for x in ["1 min","30 min","Diário"] if x in tower_file_map]
    source_keys = [x for x in ["1 min","30 min","Diário"] if x in tower_file_map]

    if processed is not None:
        source_choices.append(tr("Produtos processados", "Processed products"))
        source_keys.append("processed")

    source_display = st.selectbox(
        tr("Fonte para comparação", "Comparison source"),
        source_choices,
        key="compare_source_v29",
    )
    source_key = source_keys[source_choices.index(source_display)]

    if source_key == "processed":
        df = processed["df"]
        units = processed["units"]
        default_resolution = "Diário"
        resolutions = ["30 min","Horário","Diário","Semanal","Mensal"]
        expected = pd.Timedelta(minutes=30)
    else:
        src = get_tower_source(source_key, load_if_needed=True)
        if src is None:
            st.error(tr("Não foi possível carregar esta fonte.", "Unable to load this source."))
            st.stop()
        df = src["df"]
        units = src["units"]
        expected = expected_timedelta(source_key)
        if source_key == "1 min":
            resolutions = ["1 min","30 min","Horário","Diário","Semanal","Mensal"]
        elif source_key == "30 min":
            resolutions = ["30 min","Horário","Diário","Semanal","Mensal"]
        else:
            resolutions = ["Diário","Semanal","Mensal"]
        default_resolution = "Diário"

    vars_all = [
        c for c in df.columns
        if c not in {"TIMESTAMP","RECORD"} and
        pd.api.types.is_numeric_dtype(df[c]) and
        not is_qc(c)
    ]

    vars_ = st.multiselect(
        tr("Variáveis", "Variables"),
        vars_all,
        format_func=lambda x: unit_label(x, units),
        key="compare_vars_v29",
    )

    start, end = period_controls(
        "compare_v29",
        df["TIMESTAMP"].min(),
        df["TIMESTAMP"].max(),
    )

    c1, c2 = st.columns(2)
    resolution = c1.selectbox(
        tr("Resolução", "Resolution"),
        resolutions,
        index=resolutions.index(default_resolution) if default_resolution in resolutions else 0,
        format_func=resolution_label,
        key="compare_resolution_v29",
    )
    mode = c2.selectbox(
        tr("Forma de visualização", "Visualization mode"),
        [
            "Gráficos separados",
            "Mesmo gráfico — valores originais",
            "Dois eixos Y",
            "Normalizado (z-score)",
        ],
        format_func=comparison_mode_label,
        key="compare_mode_v29",
    )

    if len(vars_) < 2:
        st.info(tr("Selecione pelo menos duas variáveis.", "Select at least two variables."))
    elif start > end:
        st.error(tr("Período inválido.", "Invalid period."))
    else:
        sub = filter_period(df, start, end)
        data = aggregate_numeric(sub, vars_, resolution)

        if mode == "Gráficos separados":
            for v in vars_:
                line_plot(
                    data[["TIMESTAMP", v]],
                    [v], units, unit_label(v, units),
                    start, end, resolution,
                    source_expected=expected if resolution in {"1 min","30 min"} else None,
                )
        elif mode == "Mesmo gráfico — valores originais":
            line_plot(
                data, vars_, units,
                tr("Comparação de variáveis", "Variable comparison"),
                start, end, resolution,
                source_expected=expected if resolution in {"1 min","30 min"} else None,
            )
        elif mode == "Dois eixos Y":
            plot_two_y_axes(data, vars_, units, start, end, resolution)
        else:
            plot_zscore(data, vars_, start, end, resolution)

        st.subheader(tr("Estatísticas", "Statistics"))
        stats_table(sub, vars_, units)

        corr = data[vars_].corr(method="pearson", min_periods=3)
        st.subheader(tr("Correlação de Pearson", "Pearson correlation"))
        fig = px.imshow(corr, text_auto=".2f", aspect="auto", zmin=-1, zmax=1)
        st.plotly_chart(fig, width="stretch")
        st.caption(tr("Correlação não implica causalidade.", "Correlation does not imply causation."))

# ============================================================
# Preenchimento de Lacunas
# ============================================================

elif page_key == "gapfill":
    st.header(tr("Preenchimento de Lacunas", "Gap Filling"))

    if processed is None:
        st.info(tr(
            "Carregue a planilha de produtos processados para comparar séries observadas e preenchidas.",
            "Upload the processed-products workbook to compare observed and gap-filled series.",
        ))
    else:
        df = processed["df"]
        units = processed["units"]
        available = [
            b for b in GAPFILL_FAMILIES
            if f"{b}_orig" in df.columns and f"{b}_f" in df.columns
        ]
        if not available:
            st.info(tr("Nenhuma família _orig/_f encontrada.", "No _orig/_f family found."))
        else:
            base = st.selectbox(tr("Família", "Family"), available, key="gap_family_v29")
            start, end = period_controls(
                "gap_v29", df["TIMESTAMP"].min(), df["TIMESTAMP"].max()
            )
            res = st.selectbox(
                tr("Resolução", "Resolution"),
                ["30 min","Horário","Diário","Semanal","Mensal"],
                format_func=resolution_label,
                key="gap_res_v29",
            )

            if start <= end:
                sub = filter_period(df, start, end)
                orig = f"{base}_orig"
                filled = f"{base}_f"
                data = aggregate_numeric(sub, [orig, filled], res)
                line_plot(
                    data, [orig, filled], units,
                    tr(f"{base}: observado × preenchido", f"{base}: observed × gap-filled"),
                    start, end, res,
                    source_expected=pd.Timedelta(minutes=30) if res=="30 min" else None,
                )

                a = pd.to_numeric(sub[orig], errors="coerce")
                b = pd.to_numeric(sub[filled], errors="coerce")
                status = pd.Series(np.select(
                    [a.notna(), a.isna() & b.notna(), b.isna()],
                    [tr("Observado","Observed"), tr("Preenchido","Gap-filled"), tr("Ausente","Missing")],
                    default=tr("Ausente","Missing"),
                ))
                vc = status.value_counts()
                rows = []
                for label in [
                    tr("Observado","Observed"),
                    tr("Preenchido","Gap-filled"),
                    tr("Ausente","Missing"),
                ]:
                    n = int(vc.get(label, 0))
                    rows.append({
                        tr("Situação","Status"): label,
                        tr("Registros","Records"): n,
                        tr("Percentual (%)","Percentage (%)"): round(100*n/len(status),2) if len(status) else 0,
                    })
                show_table(pd.DataFrame(rows))

# ============================================================
# Balanço de Carbono
# ============================================================

elif page_key == "carbon":
    st.header(tr("Balanço de Carbono", "Carbon Balance"))

    if processed is None:
        st.info(tr(
            "Carregue a planilha de produtos processados para acessar NEE, GPP e Reco.",
            "Upload the processed-products workbook to access NEE, GPP and Reco.",
        ))
    else:
        df = processed["df"]
        units = processed["units"]
        candidates = [
            c for c in [
                "NEE", "NEE_orig", "NEE_f", "NEE_fall",
                "Reco", "Reco_DT", "GPP_f", "GPP_DT",
                "NEE_U05_f", "NEE_U50_f", "NEE_U95_f"
            ]
            if c in df.columns
        ]
        selected = st.multiselect(
            tr("Produtos de carbono", "Carbon products"),
            candidates,
            default=[c for c in ["NEE_f","Reco","GPP_f"] if c in candidates],
            format_func=lambda x: unit_label(x, units),
            key="carbon_vars_v29",
        )
        start, end = period_controls(
            "carbon_v29", df["TIMESTAMP"].min(), df["TIMESTAMP"].max()
        )
        res = st.selectbox(
            tr("Resolução", "Resolution"),
            ["30 min","Horário","Diário","Semanal","Mensal"],
            index=2,
            format_func=resolution_label,
            key="carbon_res_v29",
        )

        if selected and start <= end:
            sub = filter_period(df, start, end)
            data = aggregate_numeric(sub, selected, res)
            line_plot(
                data, selected, units,
                tr("Produtos de carbono", "Carbon products"),
                start, end, res,
                source_expected=pd.Timedelta(minutes=30) if res=="30 min" else None,
            )
            stats_table(sub, selected, units)

# ============================================================
# Qualidade dos Dados
# ============================================================

elif page_key == "qc":
    st.header(tr("Qualidade dos Dados", "Data Quality"))

    if processed is None:
        st.info(tr(
            "Carregue a planilha de produtos processados para acessar os indicadores QC.",
            "Upload the processed-products workbook to access QC indicators.",
        ))
    else:
        df = processed["df"]

        qc_vars = [
            c for c in df.columns
            if is_qc(c) and pd.api.types.is_numeric_dtype(df[c])
        ]

        if not qc_vars:
            st.info(tr(
                "Nenhuma coluna QC numérica foi encontrada na planilha processada.",
                "No numeric QC column was found in the processed workbook.",
            ))
        else:
            st.write(tr(
                "Os códigos QC abaixo são preservados exatamente como aparecem na fonte. "
                "A interpretação pelo critério de Foken é opcional.",
                "The QC codes below are preserved exactly as they appear in the source. "
                "Interpretation using Foken criteria is optional.",
            ))

            qc = st.selectbox(
                tr("Indicador QC", "QC indicator"),
                qc_vars,
                key="qc_var_v31",
            )

            start, end = period_controls(
                "qc_v31",
                df["TIMESTAMP"].min(),
                df["TIMESTAMP"].max(),
            )

            if start > end:
                st.error(tr("Período inválido.", "Invalid period."))
            else:
                sub = filter_period(df, start, end)
                raw = pd.to_numeric(sub[qc], errors="coerce")
                valid = raw.dropna()

                # -----------------------------------------------------
                # 1. QC original
                # -----------------------------------------------------
                st.subheader(tr(
                    "Códigos QC originais",
                    "Original QC codes",
                ))

                if valid.empty:
                    st.info(tr(
                        "Não há códigos QC disponíveis no período selecionado.",
                        "No QC codes are available in the selected period.",
                    ))
                else:
                    counts = valid.value_counts().sort_index()
                    total = int(counts.sum())

                    rows = []
                    for code_val, n in counts.items():
                        display_code = (
                            int(code_val)
                            if float(code_val).is_integer()
                            else float(code_val)
                        )
                        rows.append({
                            tr("Código QC original", "Original QC code"): display_code,
                            "N": int(n),
                            tr("Percentual (%)", "Percentage (%)"):
                                round(100 * int(n) / total, 2),
                        })

                    qc_table = pd.DataFrame(rows)
                    show_table(qc_table)

                    dominant = qc_table.sort_values("N", ascending=False).iloc[0]
                    c1, c2, c3 = st.columns(3)
                    c1.metric(
                        tr("Código predominante", "Dominant code"),
                        str(dominant[tr("Código QC original", "Original QC code")]),
                    )
                    c2.metric(
                        tr("Participação", "Share"),
                        f"{float(dominant[tr('Percentual (%)','Percentage (%)')]):.2f}%",
                    )
                    c3.metric(
                        tr("Códigos encontrados", "Codes found"),
                        len(qc_table),
                    )

                    fig_qc = go.Figure()
                    for code_val in sorted(valid.unique()):
                        mask = raw == code_val
                        label = (
                            str(int(code_val))
                            if float(code_val).is_integer()
                            else str(code_val)
                        )

                        fig_qc.add_trace(go.Scattergl(
                            x=sub.loc[mask, "TIMESTAMP"],
                            y=sub.loc[mask, qc],
                            mode="markers",
                            name=f"{tr('Código', 'Code')} {label}",
                            marker=dict(
                                size=6,
                                color=qc_color(code_val),
                            ),
                        ))

                    fig_qc.update_layout(
                        xaxis_title=tr("Data e hora", "Date and time"),
                        yaxis_title=tr("Código QC original", "Original QC code"),
                        height=430,
                        margin=dict(l=20, r=20, t=30, b=20),
                    )
                    fig_qc.update_xaxes(range=[start, end])
                    st.plotly_chart(fig_qc, width="stretch")

                    # -------------------------------------------------
                    # 2. Comparação opcional com Foken
                    # -------------------------------------------------
                    st.markdown("---")

                    use_foken = st.checkbox(
                        tr(
                            "Comparar com referência Foken",
                            "Compare with Foken reference",
                        ),
                        value=False,
                        key="foken_optional_v31",
                    )

                    if use_foken:
                        st.warning(tr(
                            "Esta é somente uma comparação de referência. "
                            "Não assuma que um campo `_qc`, `_fqc` ou `_fall_qc` foi gerado por Foken "
                            "sem confirmação na documentação do processamento.",
                            "This is a reference comparison only. "
                            "Do not assume that an `_qc`, `_fqc` or `_fall_qc` field was generated "
                            "using Foken criteria without confirmation in the processing documentation.",
                        ))

                        ref = pd.DataFrame([
                            {
                                tr("Escala resumida", "Summary scale"): "0",
                                tr("Escala estendida", "Extended scale"): "1–3",
                                tr("Qualidade", "Quality"): tr(
                                    "Alta qualidade", "High quality"
                                ),
                            },
                            {
                                tr("Escala resumida", "Summary scale"): "1",
                                tr("Escala estendida", "Extended scale"): "4–6",
                                tr("Qualidade", "Quality"): tr(
                                    "Qualidade moderada", "Moderate quality"
                                ),
                            },
                            {
                                tr("Escala resumida", "Summary scale"): "2",
                                tr("Escala estendida", "Extended scale"): "7–9",
                                tr("Qualidade", "Quality"): tr(
                                    "Baixa qualidade", "Low quality"
                                ),
                            },
                        ])
                        show_table(ref)

                        scale = st.selectbox(
                            tr("Escala de comparação", "Comparison scale"),
                            [
                                "Foken — 3 classes (0, 1, 2)",
                                "Foken — escala estendida (1–9)",
                            ],
                            key="foken_scale_v31",
                        )

                        def foken_class(value):
                            try:
                                x = int(float(value))
                            except Exception:
                                return "outside"

                            if scale == "Foken — 3 classes (0, 1, 2)":
                                return {
                                    0: "high",
                                    1: "moderate",
                                    2: "low",
                                }.get(x, "outside")

                            if 1 <= x <= 3:
                                return "high"
                            if 4 <= x <= 6:
                                return "moderate"
                            if 7 <= x <= 9:
                                return "low"
                            return "outside"

                        class_pt = {
                            "high": "Alta qualidade",
                            "moderate": "Qualidade moderada",
                            "low": "Baixa qualidade",
                            "outside": "Fora da escala selecionada",
                        }
                        class_en = {
                            "high": "High quality",
                            "moderate": "Moderate quality",
                            "low": "Low quality",
                            "outside": "Outside selected scale",
                        }

                        compare_rows = []
                        for code_val, n in counts.items():
                            cls = foken_class(code_val)
                            display_code = (
                                int(code_val)
                                if float(code_val).is_integer()
                                else float(code_val)
                            )
                            compare_rows.append({
                                tr("Código QC original", "Original QC code"): display_code,
                                tr("Correspondência Foken", "Foken correspondence"):
                                    class_pt[cls] if PT else class_en[cls],
                                "N": int(n),
                                tr("Percentual (%)", "Percentage (%)"):
                                    round(100 * int(n) / total, 2),
                            })

                        show_table(pd.DataFrame(compare_rows))

                    # -------------------------------------------------
                    # 3. Comparação opcional com meteorologia CR3000
                    # -------------------------------------------------
                    st.markdown("---")
                    st.subheader(tr(
                        "QC × meteorologia da torre",
                        "QC × tower meteorology",
                    ))

                    if "30 min" not in tower_file_map:
                        st.info(tr(
                            "Carregue o arquivo CR3000 de 30 minutos para habilitar esta comparação.",
                            "Upload the 30-minute CR3000 file to enable this comparison.",
                        ))
                    else:
                        use_met = st.checkbox(
                            tr(
                                "Comparar com variável micrometeorológica de 30 min",
                                "Compare with a 30-min micrometeorological variable",
                            ),
                            value=False,
                            key="qc_met_optional_v31",
                        )

                        if use_met:
                            met_src = get_tower_source("30 min", load_if_needed=True)
                            met_df = met_src["df"]
                            met_units = met_src["units"]

                            met_vars = [
                                c for c in met_df.columns
                                if c not in {"TIMESTAMP", "RECORD"}
                                and pd.api.types.is_numeric_dtype(met_df[c])
                            ]

                            if not met_vars:
                                st.info(tr(
                                    "Nenhuma variável micrometeorológica numérica foi encontrada.",
                                    "No numeric micrometeorological variable was found.",
                                ))
                            else:
                                met_var = st.selectbox(
                                    tr(
                                        "Variável micrometeorológica",
                                        "Micrometeorological variable",
                                    ),
                                    met_vars,
                                    format_func=lambda x: unit_label(x, met_units),
                                    key="qc_met_var_v31",
                                )

                                qc_pair = sub[["TIMESTAMP", qc]].copy()
                                qc_pair[qc] = pd.to_numeric(
                                    qc_pair[qc], errors="coerce"
                                )

                                met_pair = met_df[["TIMESTAMP", met_var]].copy()
                                met_pair = filter_period(
                                    met_pair, start, end
                                )
                                met_pair[met_var] = pd.to_numeric(
                                    met_pair[met_var], errors="coerce"
                                )

                                paired = pd.merge(
                                    qc_pair,
                                    met_pair,
                                    on="TIMESTAMP",
                                    how="inner",
                                )
                                paired = paired.dropna(
                                    subset=[qc, met_var]
                                ).copy()

                                st.caption(tr(
                                    f"{len(paired):,} registros pareados por timestamp exato de 30 minutos."
                                    .replace(",", "."),
                                    f"{len(paired):,} records paired by exact 30-minute timestamp.",
                                ))

                                if paired.empty:
                                    st.info(tr(
                                        "Não há registros coincidentes no período.",
                                        "There are no matching records in the period.",
                                    ))
                                else:
                                    paired["QC_label"] = paired[qc].apply(
                                        lambda x:
                                            str(int(x))
                                            if float(x).is_integer()
                                            else str(x)
                                    )

                                    st.subheader(tr(
                                        "Distribuição meteorológica por código QC",
                                        "Meteorological distribution by QC code",
                                    ))

                                    fig_box = go.Figure()
                                    for code_val in sorted(
                                        paired[qc].dropna().unique()
                                    ):
                                        mask = paired[qc] == code_val
                                        label = (
                                            str(int(code_val))
                                            if float(code_val).is_integer()
                                            else str(code_val)
                                        )
                                        fig_box.add_trace(go.Box(
                                            y=paired.loc[mask, met_var],
                                            name=f"QC {label}",
                                            marker=dict(
                                                color=qc_color(code_val)
                                            ),
                                            boxpoints=False,
                                        ))

                                    fig_box.update_layout(
                                        xaxis_title=tr(
                                            "Código QC original",
                                            "Original QC code",
                                        ),
                                        yaxis_title=unit_label(
                                            met_var, met_units
                                        ),
                                        height=450,
                                        margin=dict(
                                            l=20, r=20, t=30, b=20
                                        ),
                                    )
                                    st.plotly_chart(
                                        fig_box,
                                        width="stretch",
                                    )

                                    summary = (
                                        paired.groupby(qc)[met_var]
                                        .agg(
                                            N="count",
                                            Media="mean",
                                            Mediana="median",
                                            Desvio="std",
                                            Minimo="min",
                                            Maximo="max",
                                        )
                                        .reset_index()
                                    )

                                    if PT:
                                        summary = summary.rename(columns={
                                            qc: "Código QC original",
                                            "Media": "Média",
                                            "Desvio": "Desvio-padrão",
                                            "Minimo": "Mínimo",
                                            "Maximo": "Máximo",
                                        })
                                    else:
                                        summary = summary.rename(columns={
                                            qc: "Original QC code",
                                            "Media": "Mean",
                                            "Mediana": "Median",
                                            "Desvio": "Standard deviation",
                                            "Minimo": "Minimum",
                                            "Maximo": "Maximum",
                                        })

                                    st.subheader(tr(
                                        "Resumo por código QC",
                                        "Summary by QC code",
                                    ))
                                    show_table(summary)

                                    st.subheader(tr(
                                        "Evolução temporal conjunta",
                                        "Joint temporal evolution",
                                    ))

                                    fig_joint = go.Figure()

                                    fig_joint.add_trace(go.Scattergl(
                                        x=paired["TIMESTAMP"],
                                        y=paired[met_var],
                                        mode="lines",
                                        name=unit_label(
                                            met_var, met_units
                                        ),
                                        line=dict(
                                            color=variable_color(met_var),
                                            width=1.5,
                                        ),
                                        yaxis="y",
                                    ))

                                    for code_val in sorted(
                                        paired[qc].dropna().unique()
                                    ):
                                        mask = paired[qc] == code_val
                                        label = (
                                            str(int(code_val))
                                            if float(code_val).is_integer()
                                            else str(code_val)
                                        )

                                        fig_joint.add_trace(
                                            go.Scattergl(
                                                x=paired.loc[
                                                    mask, "TIMESTAMP"
                                                ],
                                                y=paired.loc[mask, qc],
                                                mode="markers",
                                                name=f"QC {label}",
                                                marker=dict(
                                                    color=qc_color(
                                                        code_val
                                                    ),
                                                    size=5,
                                                ),
                                                yaxis="y2",
                                            )
                                        )

                                    qc_ticks = sorted(
                                        paired[qc].dropna().unique()
                                    )

                                    fig_joint.update_layout(
                                        xaxis_title=tr(
                                            "Data e hora",
                                            "Date and time",
                                        ),
                                        yaxis=dict(
                                            title=unit_label(
                                                met_var, met_units
                                            )
                                        ),
                                        yaxis2=dict(
                                            title=tr(
                                                "Código QC original",
                                                "Original QC code",
                                            ),
                                            overlaying="y",
                                            side="right",
                                            tickmode="array",
                                            tickvals=qc_ticks,
                                        ),
                                        hovermode="x unified",
                                        height=500,
                                        margin=dict(
                                            l=20, r=20, t=30, b=20
                                        ),
                                    )
                                    fig_joint.update_xaxes(
                                        range=[start, end]
                                    )
                                    st.plotly_chart(
                                        fig_joint,
                                        width="stretch",
                                    )

                                    st.caption(tr(
                                        "A comparação é exploratória e não implica causalidade.",
                                        "The comparison is exploratory and does not imply causality.",
                                    ))

elif page_key == "about":
    st.header(tr("Sobre os Dados", "About the Data"))

    st.markdown(tr(
        """
### Camada 1 — Dados originais da torre
Arquivos Campbell Scientific **TOA5** do datalogger **CR3000**, preservando os cabeçalhos,
unidades e códigos de processamento (`Avg`, `Tot`, `Min`, `Max`, `WVc` etc.).

### Camada 2 — Eddy Covariance e QA/QC
Fluxos e indicadores de qualidade devem permanecer separados das observações meteorológicas
do datalogger, mesmo quando são pareados por timestamp.

### Camada 3 — Produtos processados
Séries preenchidas, NEE, GPP, Reco, incertezas e demais produtos derivados são apresentados
como produtos de processamento, não como observações instrumentais brutas.

### Continuidade temporal
O EcoFlux detecta lacunas reais pela diferença entre timestamps consecutivos e não desenha
uma linha contínua através dessas interrupções nas resoluções observacionais nativas.
""",
        """
### Layer 1 — Original tower data
Campbell Scientific **TOA5** files from the **CR3000** datalogger, preserving headers,
units and processing codes (`Avg`, `Tot`, `Min`, `Max`, `WVc`, etc.).

### Layer 2 — Eddy Covariance and QA/QC
Fluxes and quality indicators remain separate from datalogger meteorological observations,
even when paired by timestamp.

### Layer 3 — Processed products
Gap-filled series, NEE, GPP, Reco, uncertainties and other derived products are presented
as processing products rather than raw instrumental observations.

### Temporal continuity
EcoFlux detects real gaps from consecutive timestamps and does not draw continuous lines
through those interruptions at native observational resolutions.
"""
    ))

# ============================================================
# Solicitar Dados
# ============================================================

elif page_key == "request":
    st.header(tr("Solicitar Dados", "Request Data"))
    st.write(tr(
        "Os dados brutos não são disponibilizados para download público direto. "
        "Solicitações dependem de autorização explícita do responsável pelo conjunto de dados.",
        "Raw data are not made available for direct public download. "
        "Requests require explicit authorization from the data owner.",
    ))

    with st.form("request_form_v29"):
        nome = st.text_input(tr("Nome","Name"))
        email = st.text_input(tr("E-mail","Email"))
        inst = st.text_input(tr("Instituição","Institution"))
        purpose = st.text_area(tr("Finalidade científica / uso pretendido","Scientific purpose / intended use"))
        period = st.text_input(tr("Período de interesse","Period of interest"))
        vars_req = st.text_area(tr("Variáveis de interesse","Variables of interest"))
        submitted = st.form_submit_button(tr("Preparar solicitação","Prepare request"))

    if submitted:
        st.success(tr(
            "Solicitação preparada. Esta versão não envia nem armazena o formulário automaticamente.",
            "Request prepared. This version does not automatically send or store the form.",
        ))
