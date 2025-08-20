// PM2 Configuration for Shodo Ecosystem
// Usage: pm2 start ecosystem.config.js

module.exports = {
  apps: [
    // Frontend (React/Next.js)
    {
      name: 'shodo-frontend',
      cwd: './frontend',
      script: 'npm',
      args: 'start',
      env: {
        PORT: 8080,
        NODE_ENV: 'development'
      },
      env_production: {
        PORT: 8080,
        NODE_ENV: 'production'
      },
      max_memory_restart: '500M',
      error_file: './logs/frontend-error.log',
      out_file: './logs/frontend-out.log'
    },

    // API Gateway
    {
      name: 'shodo-api',
      cwd: './backend',
      script: 'python',
      args: 'simple_server.py',
      interpreter: 'python3',
      env: {
        PORT: 8000,
        PYTHONUNBUFFERED: 1
      },
      max_memory_restart: '1G',
      error_file: './logs/api-error.log',
      out_file: './logs/api-out.log'
    },

    // MCP Server - Shopify (example)
    // {
    //   name: 'mcp-shopify',
    //   cwd: './mcp-servers/shopify',
    //   script: 'npm',
    //   args: 'start',
    //   env: {
    //     PORT: 3001,
    //     NODE_ENV: 'development'
    //   },
    //   max_memory_restart: '300M'
    // },

    // vLLM Server (if not using Ollama)
    // {
    //   name: 'vllm-server',
    //   script: 'python',
    //   args: '-m vllm.entrypoints.openai.api_server --model mistralai/Mistral-7B-Instruct-v0.2 --port 8001',
    //   interpreter: 'python3',
    //   env: {
    //     CUDA_VISIBLE_DEVICES: '0'
    //   },
    //   max_memory_restart: '8G'
    // }
  ],

  // Deploy configuration (optional)
  deploy: {
    production: {
      user: 'deploy',
      host: 'your-server.com',
      ref: 'origin/main',
      repo: 'git@github.com:your-org/shodo-ecosystem.git',
      path: '/opt/shodo-ecosystem',
      'post-deploy': 'npm install && pm2 reload ecosystem.config.js --env production'
    }
  }
};