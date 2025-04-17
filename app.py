#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from flask import Flask, request, jsonify
import requests

app = Flask(__name__)

# 1) URLs de integração
TOKEN_URL = (
    "https://grupobmg.zeev.it/api/internal/legacy/1.0/"
    "datasource/get/1.0/"
    "qw0Xk6xWKL563BI8VvBqJiKXDN4jyNDKsseOvLMXi1FEXDGwfsSSDRJdTRFco2SrBbrg3l33pGO3FkkeH5yEuw__"
)
COMPROVANTE_URL = "https://www.accesstage.com.br/apidoc/public/v1/comprovantes"


def get_token():
    '''
    1) Solicita à URL interna do Zeev um JSON com um array em 'success'.
    2) Retorna data['success'][0]['cod'] como token.
    '''
    resp = requests.get(TOKEN_URL, timeout=10)
    resp.raise_for_status()
    payload = resp.json()
    return payload['success'][0]['cod']


@app.route("/comprovante", methods=["POST"])
def comprovante():
    '''
    Recebe JSON:
    {
      "tipoPagamento": "...",
      "codigoBancoPagador": "...",
      "numeroDocumento": "...",
      "valorPagamento": "...",
      "dataPagamento": "YYYY-MM-DD"
    }
    -> Retorna {"pdf": "...base64..."} ou {"error": "..."}.
    '''
    body = request.get_json(force=True)

    # Validação dos campos obrigatórios
    obrig = ['tipoPagamento', 'codigoBancoPagador', 'numeroDocumento', 'valorPagamento', 'dataPagamento']
    faltantes = [c for c in obrig if c not in body]
    if faltantes:
        return jsonify(error=f'Campos faltando: {", ".join(faltantes)}'), 400

    # Gera token
    try:
        token = get_token()
    except requests.HTTPError as e:
        return jsonify(error='Falha ao gerar token', details=str(e)), 502
    except Exception as e:
        return jsonify(error='Erro interno ao obter token', details=str(e)), 500

    # Prepara requisição ao AccesStage
    headers = {
        'token': token,
        'Content-Type': 'application/json'
    }
    payload = {
        'tipoPagamento':      body['tipoPagamento'],
        'codigoBancoPagador': body['codigoBancoPagador'],
        'numeroDocumento':    body['numeroDocumento'],
        'valorPagamento':     body['valorPagamento'],
        'dataPagamento':      body['dataPagamento']
    }

    # Chama API de comprovantes
    try:
        resp = requests.post(COMPROVANTE_URL, json=payload, headers=headers, timeout=10)
        resp.raise_for_status()
        data = resp.json()

        if 'pdf' in data:
            return jsonify(pdf=data['pdf']), 200
        else:
            return jsonify(error='Resposta sem campo PDF'), 502

    except requests.HTTPError as e:
        return jsonify(
            error='Documento não encontrado ou erro na API de comprovantes',
            details=e.response.text
        ), resp.status_code
    except Exception as e:
        return jsonify(error='Erro interno ao buscar comprovante', details=str(e)), 500


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
