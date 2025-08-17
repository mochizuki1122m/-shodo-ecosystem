#!/usr/bin/env python3
"""
Shodo Backend - Simple Server
最小限の依存関係で動作するシンプルなバックエンドサーバー
"""

import json
import logging
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import hashlib
import time

# ロギング設定
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# 簡易的なインメモリデータストア
users = {}
sessions = {}

class ShodoHandler(BaseHTTPRequestHandler):
    def _set_headers(self, status=200, content_type='application/json'):
        self.send_response(status)
        self.send_header('Content-Type', content_type)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type, Authorization')
        self.end_headers()

    def do_OPTIONS(self):
        self._set_headers(200)

    def do_GET(self):
        parsed_path = urlparse(self.path)
        
        if parsed_path.path == '/health':
            self._set_headers()
            response = {
                'status': 'healthy',
                'timestamp': time.time(),
                'service': 'shodo-backend'
            }
            self.wfile.write(json.dumps(response).encode())
            
        elif parsed_path.path == '/api/v1/dashboard/stats':
            self._set_headers()
            response = {
                'users': len(users),
                'sessions': len(sessions),
                'requests_today': 42,
                'active_connections': 3
            }
            self.wfile.write(json.dumps(response).encode())
            
        else:
            self._set_headers(404)
            self.wfile.write(json.dumps({'error': 'Not found'}).encode())

    def do_POST(self):
        content_length = int(self.headers['Content-Length'])
        post_data = self.rfile.read(content_length)
        
        try:
            data = json.loads(post_data)
        except json.JSONDecodeError:
            self._set_headers(400)
            self.wfile.write(json.dumps({'error': 'Invalid JSON'}).encode())
            return

        parsed_path = urlparse(self.path)
        
        if parsed_path.path == '/api/v1/auth/register':
            email = data.get('email')
            password = data.get('password')
            
            if not email or not password:
                self._set_headers(400)
                self.wfile.write(json.dumps({'error': 'Email and password required'}).encode())
                return
                
            if email in users:
                self._set_headers(400)
                self.wfile.write(json.dumps({'error': 'User already exists'}).encode())
                return
                
            # パスワードをハッシュ化（簡易版）
            password_hash = hashlib.sha256(password.encode()).hexdigest()
            users[email] = {
                'email': email,
                'password_hash': password_hash,
                'created_at': time.time()
            }
            
            self._set_headers(201)
            self.wfile.write(json.dumps({'message': 'User created', 'email': email}).encode())
            
        elif parsed_path.path == '/api/v1/auth/login':
            email = data.get('email')
            password = data.get('password')
            
            if not email or not password:
                self._set_headers(400)
                self.wfile.write(json.dumps({'error': 'Email and password required'}).encode())
                return
                
            user = users.get(email)
            if not user:
                self._set_headers(401)
                self.wfile.write(json.dumps({'error': 'Invalid credentials'}).encode())
                return
                
            password_hash = hashlib.sha256(password.encode()).hexdigest()
            if user['password_hash'] != password_hash:
                self._set_headers(401)
                self.wfile.write(json.dumps({'error': 'Invalid credentials'}).encode())
                return
                
            # セッショントークンを生成
            session_token = hashlib.sha256(f"{email}{time.time()}".encode()).hexdigest()
            sessions[session_token] = {
                'email': email,
                'created_at': time.time()
            }
            
            self._set_headers()
            self.wfile.write(json.dumps({
                'access_token': session_token,
                'token_type': 'bearer',
                'user': {'email': email}
            }).encode())
            
        elif parsed_path.path == '/api/v1/nlp/analyze':
            text = data.get('text', '')
            
            # 簡易的な自然言語解析
            intent = 'unknown'
            confidence = 0.5
            
            if 'shopify' in text.lower():
                intent = 'shopify_operation'
                confidence = 0.8
            elif 'gmail' in text.lower() or 'メール' in text:
                intent = 'gmail_operation'
                confidence = 0.8
            elif 'stripe' in text.lower() or '決済' in text:
                intent = 'stripe_operation'
                confidence = 0.8
                
            response = {
                'intent': intent,
                'confidence': confidence,
                'entities': {},
                'service': intent.split('_')[0] if '_' in intent else None,
                'suggestions': []
            }
            
            self._set_headers()
            self.wfile.write(json.dumps(response).encode())
            
        elif parsed_path.path == '/api/v1/preview/render':
            html = data.get('html', '')
            css = data.get('css', '')
            js = data.get('js', '')
            
            # 簡易的なプレビュー生成
            preview_html = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <style>{css}</style>
            </head>
            <body>
                {html}
                <script>{js}</script>
            </body>
            </html>
            """
            
            response = {
                'preview_url': 'data:text/html;base64,' + preview_html.encode().hex(),
                'status': 'success'
            }
            
            self._set_headers()
            self.wfile.write(json.dumps(response).encode())
            
        else:
            self._set_headers(404)
            self.wfile.write(json.dumps({'error': 'Not found'}).encode())

    def log_message(self, format, *args):
        logger.info("%s - %s" % (self.address_string(), format % args))

def run_server(port=8000):
    server_address = ('', port)
    httpd = HTTPServer(server_address, ShodoHandler)
    
    logger.info(f"""
╔════════════════════════════════════════╗
║     Shodo Backend Server Started       ║
╠════════════════════════════════════════╣
║ Port:   {port}                           ║
║ URL:    http://localhost:{port}          ║
╚════════════════════════════════════════╝
    """)
    
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        logger.info("Server stopped")
        httpd.server_close()

if __name__ == '__main__':
    run_server()