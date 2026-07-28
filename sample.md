## sample 
curl -X 'GET' \
  'http://localhost:8000/health' \
  -H 'accept: application/json'

http://localhost:8000/bapi/call
curl -X 'POST' \
  'http://localhost:8000/bapi/call' \
  -H 'accept: application/json' \
  -H 'X-API-Key: change-me' \
  -H 'Content-Type: application/json' \
  -d '{
  "bapi_name": "BAPI_CUSTOMER_GETLIST",
  "params": {"MAXROWS": 10}
}'