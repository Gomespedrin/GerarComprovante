# Gerador de Comprovante API

Este projeto fornece uma API REST em **Python + Flask** para:

- Gerar token via endpoint interno do Zeev  
- Consultar comprovante na API da AccesStage  
- Retornar PDF em Base64 ou mensagem de erro  

## Endpoints

### POST /comprovante

**Body JSON**:

```json
{
  "tipoPagamento": "...",
  "codigoBancoPagador": "...",
  "numeroDocumento": "...",
  "valorPagamento": "...",
  "dataPagamento": "YYYY-MM-DD"
}
```

**Resposta**:

- `200 OK`  
  ```json
  { "pdf": "<string base64>" }
  ```
- `4xx/5xx`  
  ```json
  { "error": "...", "details": "..." }
  ```

## Instalação

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python app.py
```

## Teste

Via cURL ou Postman (conforme descrito).
