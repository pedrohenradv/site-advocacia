#!/usr/bin/env python3
"""Atualiza noticias.json com as notícias mais recentes de cada área de atuação.

Fonte: feeds RSS do Google Notícias (busca por área, últimos 7 dias), filtrados
por uma lista de veículos e órgãos de referência. Somente título, veículo, data e
link são publicados no site; o texto da notícia permanece no site de origem.

Uso:  python3 scripts/atualizar_noticias.py
Sem dependências externas (apenas biblioteca padrão do Python 3.9+).
"""
import json
import re
import sys
import unicodedata
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
ARQUIVO = RAIZ / "noticias.json"
FUSO = timezone(timedelta(hours=-3))  # horário de Brasília

# ---------------------------------------------------------------- áreas e buscas
AREAS = {
    "bancario": '(banco OR bancário OR "instituição financeira" OR superendividamento OR "juros abusivos" '
                'OR consignado OR "golpe do Pix" OR "busca e apreensão" OR "cartão de crédito") '
                '(STJ OR Justiça OR tribunal OR "Banco Central" OR consumidor)',
    "criminal": '(STJ OR STF OR tribunal OR Justiça) (penal OR criminal OR "habeas corpus" OR "prisão preventiva" '
                'OR "audiência de custódia" OR "execução penal")',
    "trabalhista": '(TST OR "Justiça do Trabalho" OR trabalhista OR CLT OR FGTS OR "verbas rescisórias")',
    "civel": '(STJ OR tribunal OR Justiça) (indenização OR "dano moral" OR "Código de Defesa do Consumidor" '
             'OR contrato OR "Código Civil" OR responsabilidade civil)',
    "transito": '(CNH OR Contran OR Detran OR "multa de trânsito" OR "Código de Trânsito" OR "Lei Seca" '
                'OR "suspensão da CNH")',
    "previdenciario": '(INSS OR aposentadoria OR "benefício previdenciário" OR BPC OR "pensão por morte" '
                      'OR "auxílio por incapacidade" OR "revisão da vida toda")',
}

# Ordem de exibição em "Todas": Bancário aparece com mais frequência.
ORDEM_RODADA = ["bancario", "criminal", "trabalhista", "bancario", "civel", "transito", "previdenciario"]
MAX_POR_AREA = 5
DIAS_VALIDADE = 10          # notícias mais antigas que isso saem do site
DIAS_RESERVA = 30           # se a busca falhar, mantém as anteriores até este limite

# Somente estes veículos e órgãos são aceitos (domínio do site de origem).
FONTES_PERMITIDAS = {
    # tribunais e órgãos
    "stj.jus.br": "STJ", "stf.jus.br": "STF", "tst.jus.br": "TST", "cnj.jus.br": "CNJ",
    "tjmg.jus.br": "TJMG", "trt3.jus.br": "TRT-3", "trf6.jus.br": "TRF-6", "jus.br": None,
    "gov.br": None, "bcb.gov.br": "Banco Central", "camara.leg.br": "Câmara dos Deputados",
    "senado.leg.br": "Agência Senado", "agenciabrasil.ebc.com.br": "Agência Brasil",
    # imprensa jurídica e geral
    "conjur.com.br": "Consultor Jurídico", "migalhas.com.br": "Migalhas", "jota.info": "JOTA",
    "g1.globo.com": "g1", "globo.com": None, "folha.uol.com.br": "Folha de S.Paulo",
    "uol.com.br": None, "estadao.com.br": "Estadão", "cnnbrasil.com.br": "CNN Brasil",
    "infomoney.com.br": "InfoMoney", "valor.globo.com": "Valor Econômico",
    "exame.com": "Exame", "correiobraziliense.com.br": "Correio Braziliense",
    "otempo.com.br": "O Tempo", "em.com.br": "Estado de Minas", "metropoles.com": "Metrópoles",
    "poder360.com.br": "Poder360", "terra.com.br": "Terra", "r7.com": "R7",
    "band.uol.com.br": "Band", "istoedinheiro.com.br": "IstoÉ Dinheiro",
}

FEED = "https://news.google.com/rss/search?q={q}&hl=pt-BR&gl=BR&ceid=BR:pt-419"
UA = "Mozilla/5.0 (compatible; atualizador-noticias-site/1.0)"


def dominio_permitido(url: str):
    host = urllib.parse.urlparse(url).hostname or ""
    host = host.lower().removeprefix("www.")
    for dom in sorted(FONTES_PERMITIDAS, key=len, reverse=True):
        if host == dom or host.endswith("." + dom):
            return True, FONTES_PERMITIDAS[dom]
    return False, None


def normalizar(t: str) -> str:
    t = unicodedata.normalize("NFKD", t.lower())
    t = "".join(c for c in t if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9 ]", "", t)[:90]


def baixar(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=25) as r:
        return r.read()


def ler_feed(xml_bytes: bytes, area: str, limite: datetime):
    itens = []
    root = ET.fromstring(xml_bytes)
    for it in root.iter("item"):
        titulo = (it.findtext("title") or "").strip()
        link = (it.findtext("link") or "").strip()
        src = it.find("source")
        fonte_nome = (src.text or "").strip() if src is not None else ""
        fonte_url = src.get("url", "") if src is not None else ""
        ok, nome_padrao = dominio_permitido(fonte_url)
        if not (titulo and link and ok):
            continue
        try:
            data = parsedate_to_datetime(it.findtext("pubDate")).astimezone(FUSO)
        except Exception:
            continue
        if data < limite:
            continue
        # O Google Notícias acrescenta " - Veículo" ao fim do título.
        if fonte_nome and titulo.endswith(" - " + fonte_nome):
            titulo = titulo[: -(len(fonte_nome) + 3)].strip()
        itens.append({
            "area": area,
            "data": data.strftime("%Y-%m-%d"),
            "titulo": titulo,
            "resumo": "",
            "url": link,
            "fonte": nome_padrao or fonte_nome or "Fonte",
            "_ts": data.timestamp(),
        })
    return itens


def montar(por_area: dict):
    vistos, saida = set(), []
    filas = {a: sorted(v, key=lambda x: x["_ts"], reverse=True) for a, v in por_area.items()}
    for a in filas:  # remove duplicadas dentro e entre áreas
        unicos = []
        for n in filas[a]:
            k = normalizar(n["titulo"])
            if k in vistos:
                continue
            vistos.add(k)
            unicos.append(n)
        filas[a] = unicos[:MAX_POR_AREA]
    while any(filas.values()):
        for a in ORDEM_RODADA:
            if filas.get(a):
                saida.append(filas[a].pop(0))
    for n in saida:
        n.pop("_ts", None)
    return saida


def main(arquivos_teste=None):
    agora = datetime.now(FUSO)
    limite = agora - timedelta(days=DIAS_VALIDADE)
    anteriores = {}
    if ARQUIVO.exists():
        try:
            for n in json.loads(ARQUIVO.read_text("utf-8")).get("itens", []):
                anteriores.setdefault(n["area"], []).append(n)
        except Exception:
            pass

    por_area, falhas = {}, []
    for area, consulta in AREAS.items():
        try:
            if arquivos_teste:
                xml = Path(arquivos_teste[area]).read_bytes()
            else:
                xml = baixar(FEED.format(q=urllib.parse.quote(consulta + " when:7d")))
            por_area[area] = ler_feed(xml, area, limite)
        except Exception as e:  # rede fora, feed alterado etc.
            falhas.append(f"{area}: {e}")
            por_area[area] = []
        if not por_area[area]:  # mantém as anteriores ainda recentes
            reserva_lim = (agora - timedelta(days=DIAS_RESERVA)).strftime("%Y-%m-%d")
            por_area[area] = [dict(n, _ts=datetime.fromisoformat(n["data"]).timestamp())
                              for n in anteriores.get(area, []) if n.get("data", "") >= reserva_lim]

    itens = montar(por_area)
    if not itens:
        print("Nenhuma notícia obtida; arquivo mantido sem alterações.", file=sys.stderr)
        return 1
    ARQUIVO.write_text(json.dumps({"atualizado_em": agora.strftime("%Y-%m-%d"), "itens": itens},
                                  ensure_ascii=False, indent=1), "utf-8")
    print(f"{len(itens)} notícias gravadas em {ARQUIVO.name}.")
    for f in falhas:
        print("Aviso:", f, file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
