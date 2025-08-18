import DOMPurify from 'dompurify';

// CSPセーフな設定でDOMPurifyを初期化
const createSanitizer = () => {
  // 許可するタグとプロパティを厳格に制限
  const config: DOMPurify.Config = {
    ALLOWED_TAGS: [
      'div', 'span', 'p', 'a', 'img', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
      'ul', 'ol', 'li', 'blockquote', 'pre', 'code', 'table', 'thead', 'tbody',
      'tr', 'th', 'td', 'strong', 'em', 'br', 'hr', 'button', 'form', 'input',
      'label', 'select', 'option', 'textarea'
    ],
    ALLOWED_ATTR: [
      'href', 'src', 'alt', 'title', 'class', 'id', 'style',
      'type', 'name', 'value', 'placeholder', 'for', 'disabled',
      'readonly', 'checked', 'selected', 'data-*'
    ],
    ALLOW_DATA_ATTR: true,
    ALLOW_ARIA_ATTR: true,
    KEEP_CONTENT: true,
    SAFE_FOR_TEMPLATES: true,
    SANITIZE_DOM: true,
    RETURN_DOM: false,
    RETURN_DOM_FRAGMENT: false,
    RETURN_TRUSTED_TYPE: false,
    FORCE_BODY: false,
    IN_PLACE: false
  };

  return (dirty: string): string => {
    // スタイル属性の危険なプロパティを除去
    const clean = DOMPurify.sanitize(dirty, config);
    
    // 追加のセキュリティチェック
    // JavaScriptプロトコルの除去
    const noJsProtocol = clean.replace(/javascript:/gi, '');
    
    // data: URLの制限（画像のみ許可）
    const safeDataUrls = noJsProtocol.replace(
      /data:(?!image\/(png|jpg|jpeg|gif|svg\+xml|webp))/gi,
      ''
    );
    
    return safeDataUrls;
  };
};

// CSS注入対策
export const sanitizeCSS = (css: string): string => {
  // 危険なCSSプロパティとバリューを除去
  const dangerousPatterns = [
    /javascript:/gi,
    /expression\s*\(/gi,
    /@import/gi,
    /@charset/gi,
    /behavior:/gi,
    /-moz-binding:/gi,
    /javascript:/gi,
    /vbscript:/gi
  ];
  
  let safeCss = css;
  dangerousPatterns.forEach(pattern => {
    safeCss = safeCss.replace(pattern, '');
  });
  
  return safeCss;
};

// HTMLサニタイザーのエクスポート
export const sanitizeHTML = createSanitizer();

// プレビュー用の特別なサニタイザー（より制限的）
export const sanitizePreview = (html: string): string => {
  const previewConfig: DOMPurify.Config = {
    ALLOWED_TAGS: [
      'div', 'span', 'p', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
      'ul', 'ol', 'li', 'strong', 'em', 'br', 'hr'
    ],
    ALLOWED_ATTR: ['class', 'id', 'style'],
    FORBID_TAGS: ['script', 'iframe', 'object', 'embed', 'form'],
    FORBID_ATTR: ['onerror', 'onload', 'onclick', 'onmouseover']
  };
  
  return DOMPurify.sanitize(html, previewConfig);
};

// JSONレスポンスのサニタイズ
export const sanitizeJSON = (data: any): any => {
  if (typeof data === 'string') {
    return sanitizeHTML(data);
  }
  
  if (Array.isArray(data)) {
    return data.map(item => sanitizeJSON(item));
  }
  
  if (data && typeof data === 'object') {
    const sanitized: any = {};
    for (const key in data) {
      if (data.hasOwnProperty(key)) {
        sanitized[key] = sanitizeJSON(data[key]);
      }
    }
    return sanitized;
  }
  
  return data;
};

// CSPヘッダーの生成
export const generateCSPHeader = (): string => {
  const policies = [
    "default-src 'self'",
    "script-src 'self' 'unsafe-inline' 'unsafe-eval'", // React開発環境用
    "style-src 'self' 'unsafe-inline'",
    "img-src 'self' data: https:",
    "font-src 'self'",
    "connect-src 'self' http://localhost:* ws://localhost:*", // 開発環境用
    "frame-ancestors 'none'",
    "base-uri 'self'",
    "form-action 'self'"
  ];
  
  return policies.join('; ');
};