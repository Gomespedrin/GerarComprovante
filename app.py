from flask import Flask, request, jsonify
import requests
from cachetools import TTLCache
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

app = Flask(__name__)

# --- Cache em memória para o token (1 entrada, TTL=3600s = 1 hora) ---
token_cache = TTLCache(maxsize=1, ttl=3600)

# --- Sessão HTTP com retry/backoff para 502/503/504 ---
session = requests.Session()
retry_strategy = Retry(
    total=3,
    backoff_factor=1,
    status_forcelist=[502, 503, 504],
    allowed_methods=["GET", "POST"]
)
adapter = HTTPAdapter(max_retries=retry_strategy)
session.mount("https://", adapter)
session.mount("http://", adapter)

# --- URLs externas (tire da conversa / ajuste conforme seu ambiente) ---
TOKEN_URL = (
    "https://grupobmg.zeev.it/"
    "api/internal/legacy/1.0/datasource/get/1.0/"
    "qw0Xk6xWKL563BI8VvBqJiKXDN4jyNDKsseOvLMXi1FEXDGwfsSSDRJdTRFco2SrBbrg3l33pGO3FkkeH5yEuw__"
)
COMPROVANTE_URL = "https://www.accesstage.com.br/apidoc/public/v1/comprovantes"

def get_token():
    """Busca ou retorna do cache um token válido."""
    if "token" in token_cache:
        return token_cache["token"]
    try:
        resp = session.get(TOKEN_URL, timeout=30)
        resp.raise_for_status()
        body = resp.json()
        token = body["success"][0]["cod"]
        token_cache["token"] = token
        return token
    except Exception as e:
        # dispara um erro controlado para ser capturado
        raise RuntimeError(f"Não foi possível gerar token: {e}")

@app.route("/comprovante", methods=["POST"])
def gerar_comprovante():
    """
    Espera JSON:
    {
      "tipoDePagamento": "20",
      "codBan": "341",
      "numeroDoDocumento": "...",
      "valorDoPagamento": "412,5",
      "dataDoPagamento": "07/04/2025"
    }
    Retorna:
    - 200 + { Resultado, link }
    - 4xx ou 5xx + { Resultado, motivo }
    """
    try:
        payload_in = request.get_json(force=True)
    except:
        return jsonify(Resultado="Erro", motivo="JSON inválido"), 400

    # 1) Obter token
    try:
        token = get_token()
    except RuntimeError as e:
        return jsonify(Resultado="Erro", motivo=str(e)), 502

    # 2) Validar e converter campos
    try:
        # data: dd/MM/yyyy -> yyyy-MM-dd
        d, m, y = payload_in["dataDoPagamento"].split("/")
        data_iso = f"{y}-{m.zfill(2)}-{d.zfill(2)}"
        # valor: "1.234,56" -> "1234.56"
        valor = payload_in["valorDoPagamento"].replace(".", "").replace(",", ".")
        payload = {
            "tipoPagamento": payload_in["tipoDePagamento"],
            "codigoBancoPagador": payload_in["codBan"],
            "numeroDocumento": payload_in["numeroDoDocumento"],
            "valorPagamento": valor,
            "dataPagamento": data_iso
        }
    except KeyError:
        return jsonify(Resultado="Erro", motivo="Campo ausente"), 400
    except Exception:
        return jsonify(Resultado="Erro", motivo="Formato de data/valor inválido"), 400

    # 3) Chamar Accesstage
    headers = {"token": token, "Content-Type": "application/json"}
    try:
        resp = session.post(COMPROVANTE_URL, json=payload, headers=headers, timeout=30)

        if resp.status_code == 404:
            return jsonify(Resultado="Erro", motivo="Comprovante não encontrado."), 404

        resp.raise_for_status()
        body = resp.json()

        pdf_b64 = body.get("pdf")
        if not pdf_b64:
            # se a API vier sem pdf
            raise ValueError("Resposta sem PDF em base64")

        link = f"data:application/pdf;base64,{pdf_b64}"
        return jsonify(Resultado="Comprovante encontrado", link=link), 200

    except requests.HTTPError as e:
        # 4xx / 5xx diferente de 404
        return jsonify(Resultado="Erro", motivo=f"Erro na API de comprovantes: {e}"), 502

    except Exception as e:
        # timeout, JSON inválido, etc.
        return jsonify(Resultado="Erro", motivo=f"Falha inesperada: {e}"), 500

if __name__ == "__main__":
    # no Render, o gunicorn executa; localmente basta:
    app.run(host="0.0.0.0", port=5000, debug=False)
