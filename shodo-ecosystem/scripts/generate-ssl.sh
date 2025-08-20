#!/bin/bash

# SSL証明書生成スクリプト（開発環境用）
# 本番環境では Let's Encrypt や正式な証明書を使用してください

set -e

echo "🔐 Generating SSL certificates for development..."

# SSL証明書ディレクトリの作成
mkdir -p nginx/ssl

# 秘密鍵の生成
echo "📝 Generating private key..."
openssl genrsa -out nginx/ssl/key.pem 2048

# 証明書署名要求（CSR）の生成
echo "📋 Generating certificate signing request..."
openssl req -new -key nginx/ssl/key.pem -out nginx/ssl/cert.csr -subj "/C=JP/ST=Tokyo/L=Tokyo/O=Shodo Ecosystem/OU=Development/CN=localhost"

# 自己署名証明書の生成（365日有効）
echo "📜 Generating self-signed certificate..."
openssl x509 -req -days 365 -in nginx/ssl/cert.csr -signkey nginx/ssl/key.pem -out nginx/ssl/cert.pem

# Subject Alternative Name (SAN) 対応の証明書生成
echo "🌐 Generating SAN certificate for multiple domains..."
cat > nginx/ssl/cert.conf << EOF
[req]
distinguished_name = req_distinguished_name
req_extensions = v3_req
prompt = no

[req_distinguished_name]
C = JP
ST = Tokyo
L = Tokyo
O = Shodo Ecosystem
OU = Development
CN = localhost

[v3_req]
keyUsage = keyEncipherment, dataEncipherment
extendedKeyUsage = serverAuth
subjectAltName = @alt_names

[alt_names]
DNS.1 = localhost
DNS.2 = shodo.local
DNS.3 = *.shodo.local
DNS.4 = 127.0.0.1
IP.1 = 127.0.0.1
IP.2 = ::1
EOF

# SAN証明書の生成
openssl req -new -x509 -key nginx/ssl/key.pem -out nginx/ssl/cert.pem -days 365 -config nginx/ssl/cert.conf -extensions v3_req

# CSRファイルの削除
rm nginx/ssl/cert.csr nginx/ssl/cert.conf

# 権限設定
chmod 600 nginx/ssl/key.pem
chmod 644 nginx/ssl/cert.pem

echo "✅ SSL certificates generated successfully!"
echo ""
echo "📁 Files created:"
echo "   - nginx/ssl/key.pem  (private key)"
echo "   - nginx/ssl/cert.pem (certificate)"
echo ""
echo "🚨 WARNING: These are self-signed certificates for DEVELOPMENT ONLY!"
echo "   For production, use Let's Encrypt or a trusted CA."
echo ""
echo "🔧 To trust the certificate in your browser:"
echo "   1. Open https://localhost in your browser"
echo "   2. Click 'Advanced' -> 'Proceed to localhost (unsafe)'"
echo "   3. Or add the certificate to your system's trusted store"
echo ""
echo "📋 Certificate info:"
openssl x509 -in nginx/ssl/cert.pem -text -noout | grep -A 5 "Subject:"
echo ""
echo "🎉 Ready for HTTPS development!"