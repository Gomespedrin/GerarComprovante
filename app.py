#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from flask import Flask, request, jsonify
import requests
from requests.exceptions import Timeout, HTTPError

app = Flask(__name__)

TOKEN_URL = (
    "https://grupobmg.zeev.it/api/internal/legacy/1.0/"
    "datasource/get/1.0/"
    "qw0Xk6xWKL563BI8VvBqJiKXDN4jyNDKsseOvLMXi1FEXDGwfsSSDRJdTRFco2SrBbrg3l33pGO3FkkeH5yEuw__"
)
COMPROVANTE_URL = "https://www.accesstage.com.br/apidoc/public/v1/comprovantes"

def get_token():
    resp = requests.get(TOKEN_URL, timeout=10)
    resp.raise_for_status()
    return resp.json()["success"][0]["cod"]

@app.route("/comprovante", methods=["POST"])
def comprovante():
    body = request.get_json(force=True)
    # validação campos…
    obrig = ["tipoPagamento","codigoBancoPagador","numeroDocumento","valorPagamento","dataPagamento"]
    falt = [c for c in obrig if c not in body]
    if falt:
        return jsonify(error=f"Campos faltando: {', '.join(falt)}"), 400

    try:
        token = get_token()
    except HTTPError as e:
        return jsonify(error="Falha ao gerar token", details=str(e)), 502
    except Exception as e:
        return jsonify(error="Erro interno ao obter token", details=str(e)), 500

    headers = {"token": token, "Content-Type": "application/json"}
    payload = {k: body[k] for k in obrig}

    try:
        # timeout=(connect_timeout, read_timeout)
        resp = requests.post(COMPROVANTE_URL, json=payload, headers=headers, timeout=(5, 30))
        resp.raise_for_status()
        data = resp.json()
        if "pdf" in data:
            return jsonify(pdf=data["pdf"]), 200
        else:
            return jsonify(error="Resposta sem campo PDF"), 502

    except Timeout as e:
        return jsonify(error="Timeout ao chamar API de comprovantes", details=str(e)), 504
    except HTTPError as e:
        return jsonify(
            error="Documento não encontrado ou erro na API de comprovantes",
            details=e.response.text
        ), resp.status_code
    except Exception as e:
        return jsonify(error="Erro interno ao buscar comprovante", details=str(e)), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
