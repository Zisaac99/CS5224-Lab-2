#!/bin/bash
# EC2 user data (Amazon Linux 2023): install Docker, fetch the backend from S3, build and run it.
# Credentials come from the instance profile (Lab2BackendEC2Profile); launch with
# HttpPutResponseHopLimit=2 so the container can reach the instance metadata service.
set -euxo pipefail

BUCKET=cs5224-lab2-a0301596a
REGION=ap-southeast-1
WEB_ORIGIN=http://cs5224-lab2-web-a0301596a.s3-website-ap-southeast-1.amazonaws.com

dnf install -y docker
systemctl enable --now docker

mkdir -p /opt/lab2 && cd /opt/lab2
aws s3 cp "s3://$BUCKET/deploy/lab2-backend.tgz" . --region "$REGION"
tar xzf lab2-backend.tgz

docker build -f backend/Dockerfile -t lab2-backend .
docker rm -f lab2-backend 2>/dev/null || true
docker run -d --name lab2-backend --restart always -p 8000:8000 \
  -e AWS_REGION="$REGION" -e BUCKET="$BUCKET" \
  -e CORS_ORIGINS="$WEB_ORIGIN,http://localhost:5173" \
  lab2-backend
