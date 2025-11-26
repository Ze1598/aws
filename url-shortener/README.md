# url-shortener

## Goal

Build a Bitly-style URL shortener on AWS using API Gateway + Lambda + DynamoDB.

## Outcome

A live API that creates short links (`POST /shorten`) and redirects them (`GET /{code}`).

## Resources Created

### IAM Roles

Custom IAM role for the lambdas interactions with DynamoDB.

![alt text](lambda-urlshortener-role.png)

### DynamoDB

One table to store generated URL short codes and original URLs.

[alt text](dynamodb-table.png)

### Lambda

One lambda for generating the URL short code (POST), and another to allow the redirect (GET).

Code for each lambda is available in  [urlshortener-redirect.py](urlshortener-shorten.py) and [urlshortener-redirect.py](urlshortener-redirect.py)

![alt text](urlshortener-shorten.png)
![alt text](urlshortener-redirect.png)

### API Gateway

A REST API created and supported by lambda proxies. Two endpoints created:

#### (POST) /shorten

Receives a URL, generates a record for the DynamoDB table with a new shortcode and returns the shortened URL

![alt text](api-gateway-endpoints-post.png)

#### (GET) /{shortCode}

Receives the shortCode as a URL parameter, lookups the original URL in DynamoDB and redirects the user to it

![alt text](api-gateway-endpoints-get.png)