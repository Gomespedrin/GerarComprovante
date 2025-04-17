#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from flask import Flask, request, jsonify, Response, url_for
import requests, base64
from datetime import datetime
from requests.exceptions import Timeout, HTTPError

app = Flask(__name__)

TOKEN_URL = (
    "https://grupobmg.zeev.it/api/internal/legacy/1.0/"
    "datasource/get/1.0/"
    "qw0Xk6xWKL563BI8VvBqJiKXDN4jyNDKsseOvLMXi1FEXDGwfsSSDRJdTRFco2SrBbrg3l33pGO3FkkeH5yEuw__"
)
COMPROVANTE_URL = "https://www.accesstage.com.br/apidoc/public/v1/comprovantes"

# Em memória armazenamos o último PDF (só para demo; em produção use S3, BD, etc.)
_last_pdf = None

def get_token():
    r = requests.get(TOKEN_URL, timeout=10)
    r.raise_for_status()
    return r.json()["success"][0]["cod"]

@app.route("/comprovante", methods=["POST"])
def comprovante():
    global _last_pdf
    body = request.get_json(force=True)

    # --- 1) Normalizar os campos vindos do Zeev ---
    # Exemplo de JSON bruto do Zeev:
    # {
    #   "tipoDePagamento": "20",
    #   "codBan":         "341",
    #   "numeroDoDocumento":"25D3000008DPM004502S",
    #   "valorDoPagamento": "412,5",
    #   "dataDoPagamento":  "07/04/2025"
    # }

    try:
        tipo =   body["tipoDePagamento"]
        banco =  body["codBan"]
        num   =  body["numeroDoDocumento"]
        # 1a) converte "412,5" → "412.50"
        valor = body["valorDoPagamento"].replace(".", "").replace(",", ".")
        # 1b) converte "07/04/2025" → "2025-04-07"
        data  = datetime.strptime(body["dataDoPagamento"], "%d/%m/%Y").date().isoformat()
    except KeyError as e:
        return jsonify(error=f"Campo obrigatório faltando: {e}"), 400
    except ValueError as e:
        return jsonify(error="Formato inválido em valor ou data", details=str(e)), 400

    # 2) Gera token e chama AccesStage
    try:
        token = get_token()
    except Exception as e:
        return jsonify(error="Não foi possível gerar token", details=str(e)), 502

    headers = {"token": token, "Content-Type": "application/json"}
    payload = {
        "tipoPagamento":      tipo,
        "codigoBancoPagador": banco,
        "numeroDocumento":    num,
        "valorPagamento":     valor,
        "dataPagamento":      data
    }

    try:
        r = requests.post(COMPROVANTE_URL, json=payload, headers=headers, timeout=(5,30))
        r.raise_for_status()
        data_json = r.json()
        if "pdf" not in data_json:
            return jsonify(error="Resposta sem campo PDF"), 502

        # salva em memória para servir no download
        _last_pdf = data_json["pdf"]
        # gera a URL de download (rota /comprovante/download)
        link = url_for("download_comprovante", _external=True)
        return jsonify(pdfBase64=_last_pdf, pdfLink=link), 200

    except Timeout as e:
        return jsonify(error="Timeout na API de comprovantes", details=str(e)), 504
    except HTTPError as e:
        return jsonify(
            error="Erro na API de comprovantes",
            details=e.response.text
        ), r.status_code
    except Exception as e:
        return jsonify(error="Erro interno", details=str(e)), 500

@app.route("/comprovante/download", methods=["GET"])
def download_comprovante():
    """
    Retorna o PDF gerado na última chamada como um download.
    Em produção, este endpoint deveria buscar por ID ou armazenar em S3/BD.
    """
    global _last_pdf
    if not _last_pdf:
        return "Nenhum comprovante gerado ainda.", 404

    pdf_bytes = base64.b64decode(_last_pdf)
    return Response(
        pdf_bytes,
        mimetype="application/pdf",
        headers={"Content-Disposition": 'attachment; filename="comprovante.pdf"'}
    )

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
