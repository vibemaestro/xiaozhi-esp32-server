#!/bin/bash
mkdir -p ../ssl
if [ ! -f ../ssl/server.key ]; then
    echo "Generating self-signed SSL certificates..."
    openssl req -x509 -newkey rsa:4096 -keyout ../ssl/server.key \
    -out ../ssl/server.crt -days 365 -nodes \
    -subj "/C=VN/ST=Hanoi/L=Hanoi/O=Betinyai/OU=IT/CN=betinyai.vn"
    echo "SSL certificates generated at ../ssl/"
fi