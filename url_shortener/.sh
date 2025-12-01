curl -sS -X POST \
  -H "Content-Type: application/json" \
  -d '{"url":"https://aws.amazon.com"}' \
  https://<invoke-id>.execute-api.<region>.amazonaws.com/prod/shorten

# Expected result
# {"shortUrl":"https://<invoke-id>.execute-api.<region>.amazonaws.com/prod/Ab12Cd","code":"Ab12Cd"}


curl -I https://<invoke-id>.execute-api.<region>.amazonaws.com/prod/<code>

