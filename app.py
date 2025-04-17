from flask import Flask, request, jsonify
import requests
from cachetools import TTLCache
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

app = Flask(__name__)

# Cache para token: 1 entrada, TTL de 1 hora
token_cache = TTLCache(maxsize=1, ttl=3600)

# Sessão HTTP com retry para 502/503/504
def create_session():
    session = requests.Session()
    retry = Retry(
        total=3,
        backoff_factor=1,
        status_forcelist=[502, 503, 504],
        allowed_methods=["GET", "POST"]
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session

session = create_session()

# URLs externas
token_url = (
    "https://grupobmg.zeev.it/api/internal/legacy/1.0/datasource/get/1.0/"
    "qw0Xk6xWKL563BI8VvBqJiKXDN4jyNDKsseOvLMXi1FEXDGwfsSSDRJdTRFco2SrBbrg3l33pGO3FkkeH5yEuw__"
)
comprovante_url = "https://www.accesstage.com.br/apidoc/public/v1/comprovantes"


def get_token():
    if "token" in token_cache:
        return token_cache["token"]
    try:
        resp = session.get(token_url, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        token = data["success"][0]["cod"]
        token_cache["token"] = token
        return token
    except Exception as e:
        raise RuntimeError(f"Não foi possível gerar token: {e}")


@app.route('/comprovante', methods=['POST'])
def gerar_comprovante():
    # Lê JSON de entrada
    try:
        body = request.get_json(force=True)
    except Exception:
        return jsonify(Resultado="Erro", motivo="JSON inválido"), 400

    # Obter token
    try:
        token = get_token()
    except RuntimeError as e:
        return jsonify(Resultado="Erro", motivo=str(e)), 502

    # Converter data e valor
    try:
        d, m, y = body['dataDoPagamento'].split('/')
        data_iso = f"{y}-{m.zfill(2)}-{d.zfill(2)}"
        valor = body['valorDoPagamento'].replace('.', '').replace(',', '.')
        payload = {
            'tipoPagamento': body['tipoDePagamento'],
            'codigoBancoPagador': body['codBan'],
            'numeroDocumento': body['numeroDoDocumento'],
            'valorPagamento': valor,
            'dataPagamento': data_iso
        }
    except KeyError:
        return jsonify(Resultado="Erro", motivo="Campo ausente"), 400
    except Exception:
        return jsonify(Resultado="Erro", motivo="Formato de data/valor inválido"), 400

    # Chamada à API de comprovantes
    headers = {'token': token, 'Content-Type': 'application/json'}
    try:
        resp = session.post(comprovante_url, json=payload, headers=headers, timeout=30)
        if resp.status_code == 404:
            return jsonify(Resultado="Erro", motivo="Comprovante não encontrado."), 404
        resp.raise_for_status()
        data = resp.json()
        pdf_b64 = data.get('pdf')
        if not pdf_b64:
            raise ValueError('Resposta sem PDF em base64')
        # Monta o link para download
        link = f"data:application/pdf;base64,{pdf_b64}"
        return jsonify(Resultado="Comprovante encontrado", link=link), 200
    except requests.HTTPError as e:
        return jsonify(Resultado="Erro", motivo=f"Erro na API de comprovantes: {e}"), 502
    except Exception as e:
        return jsonify(Resultado="Erro", motivo=f"Falha inesperada: {e}"), 500


if __name__ == '__main__':
    # Em produção, usamos gunicorn; localmente:
    app.run(host='0.0.0.0', port=5000, debug=False)
