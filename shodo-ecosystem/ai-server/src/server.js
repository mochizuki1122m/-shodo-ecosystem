import Fastify from 'fastify';
import cors from '@fastify/cors';
import { Ollama } from 'ollama';
import OpenAI from 'openai';
import dotenv from 'dotenv';
import { createHash, randomUUID } from 'crypto';
import client from 'prom-client';

dotenv.config();

const fastify = Fastify({
  logger: {
    transport: {
      target: 'pino-pretty',
      options: {
        translateTime: 'HH:MM:ss Z',
        ignore: 'pid,hostname',
      },
    },
  },
});

// CORS設定（環境変数駆動）
const NODE_ENV = process.env.NODE_ENV || 'development';
const ALLOWED_ORIGINS = (process.env.ALLOWED_ORIGINS || '').split(',').map((s) => s.trim()).filter(Boolean);
await fastify.register(cors, {
  origin: (origin, cb) => {
    if (!origin) return cb(null, true); // SSR/同一オリジン
    if (NODE_ENV === 'production') {
      if (ALLOWED_ORIGINS.length > 0 && ALLOWED_ORIGINS.includes(origin)) {
        return cb(null, true);
      }
      return cb(new Error('Not allowed by CORS'), false);
    }
    // 開発は緩め
    cb(null, true);
  },
  credentials: true,
});

// ===== Correlation ID middleware =====
fastify.addHook('onRequest', async (request, reply) => {
  let cid = request.headers['x-correlation-id'];
  if (!cid) cid = randomUUID();
  request.headers['x-correlation-id'] = cid;
  reply.header('X-Correlation-ID', cid);
});

// ===== Simple in-memory rate limit (per IP) =====
const RATE_LIMIT_RPM = Number(process.env.RATE_LIMIT_RPM || 120);
const rateStore = new Map(); // key -> { count, reset }
fastify.addHook('onRequest', async (request, reply) => {
  if (RATE_LIMIT_RPM <= 0) return;
  const ip = (request.headers['x-forwarded-for'] || request.ip || 'unknown').toString().split(',')[0].trim();
  const now = Date.now();
  const key = ip;
  let entry = rateStore.get(key);
  if (!entry || now > entry.reset) {
    entry = { count: 0, reset: now + 60_000 };
    rateStore.set(key, entry);
  }
  entry.count += 1;
  if (entry.count > RATE_LIMIT_RPM) {
    const retryAfter = Math.ceil((entry.reset - now) / 1000);
    reply.header('Retry-After', retryAfter.toString());
    reply.header('X-RateLimit-Limit', RATE_LIMIT_RPM.toString());
    reply.header('X-RateLimit-Remaining', '0');
    reply.header('X-RateLimit-Reset', Math.floor(entry.reset / 1000).toString());
    return reply.code(429).send({ error: 'rate_limited', message: 'Too many requests' });
  }
  reply.header('X-RateLimit-Limit', RATE_LIMIT_RPM.toString());
  reply.header('X-RateLimit-Remaining', Math.max(0, RATE_LIMIT_RPM - entry.count).toString());
});

// ===== Prometheus metrics =====
client.collectDefaultMetrics();
const httpRequestCounter = new client.Counter({
  name: 'ai_server_http_requests_total',
  help: 'Total number of HTTP requests',
  labelNames: ['method', 'route', 'status']
});
const inferenceTokens = new client.Counter({
  name: 'ai_server_inference_tokens_total',
  help: 'Total tokens processed by inference',
  labelNames: ['engine', 'type']
});

fastify.addHook('onResponse', async (request, reply) => {
  try {
    httpRequestCounter.inc({ method: request.method, route: request.routerPath || request.url, status: reply.statusCode });
  } catch {}
});

fastify.get('/metrics', async (request, reply) => {
  reply.header('Content-Type', await client.register.contentType);
  return client.register.metrics();
});

// 推論エンジンの選択
const INFERENCE_ENGINE = process.env.INFERENCE_ENGINE || 'ollama';
const MODEL_NAME = process.env.MODEL_NAME || 'llama2:7b-chat';

// Ollama クライアント
const ollama = new Ollama({
  host: process.env.OLLAMA_HOST || 'http://localhost:11434',
});

// vLLM クライアント（OpenAI互換API）
const vllm = new OpenAI({
  baseURL: process.env.VLLM_URL || 'http://localhost:8001/v1',  // ポートを8001に統一
  apiKey: 'dummy', // vLLMはAPIキー不要
});

// ヘルスチェック
fastify.get('/health', async (request, reply) => {
  return {
    status: 'healthy',
    engine: INFERENCE_ENGINE,
    model: MODEL_NAME,
    timestamp: new Date().toISOString(),
  };
});

// モデル一覧
fastify.get('/v1/models', async (request, reply) => {
  if (INFERENCE_ENGINE === 'ollama') {
    const models = await ollama.list();
    return {
      object: 'list',
      data: models.models.map(m => ({
        id: m.name,
        object: 'model',
        created: Date.parse(m.modified_at) / 1000,
        owned_by: 'ollama',
      })),
    };
  } else {
    const models = await vllm.models.list();
    return models;
  }
});

// テキスト補完
fastify.post('/v1/completions', async (request, reply) => {
  const { prompt, max_tokens = 2048, temperature = 0.7, stream = false } = request.body;

  if (INFERENCE_ENGINE === 'ollama') {
    const response = await ollama.generate({
      model: MODEL_NAME,
      prompt,
      options: {
        temperature,
        num_predict: max_tokens,
      },
      stream,
    });

    if (stream) {
      reply.raw.setHeader('Content-Type', 'text/event-stream');
      reply.raw.setHeader('Cache-Control', 'no-cache');
      reply.raw.setHeader('Connection', 'keep-alive');

      for await (const part of response) {
        inferenceTokens.inc({ engine: 'ollama', type: 'completion' }, (part?.response || '').split(' ').length || 0);
        reply.raw.write(`data: ${JSON.stringify({
          choices: [{ text: part.response, index: 0 }],
        })}\n\n`);
      }
      reply.raw.end();
    } else {
      inferenceTokens.inc({ engine: 'ollama', type: 'completion' }, (prompt.split(' ').length || 0) + ((response.response || '').split(' ').length || 0));
      return {
        id: `cmpl-${Date.now()}`,
        object: 'text_completion',
        created: Math.floor(Date.now() / 1000),
        model: MODEL_NAME,
        choices: [{
          text: response.response,
          index: 0,
          logprobs: null,
          finish_reason: 'stop',
        }],
        usage: {
          prompt_tokens: prompt.split(' ').length,
          completion_tokens: response.response.split(' ').length,
          total_tokens: prompt.split(' ').length + response.response.split(' ').length,
        },
      };
    }
  } else {
    // vLLM使用
    const completion = await vllm.completions.create({
      model: MODEL_NAME,
      prompt,
      max_tokens,
      temperature,
      stream,
    });
    // usage計測（概算）
    inferenceTokens.inc({ engine: 'vllm', type: 'completion' }, (prompt.split(' ').length || 0));
    return completion;
  }
});

// チャット補完（ChatGPT互換）
fastify.post('/v1/chat/completions', async (request, reply) => {
  const { messages, max_tokens = 2048, temperature = 0.7, stream = false } = request.body;

  // メッセージを単一プロンプトに変換
  const prompt = messages.map(m => `${m.role}: ${m.content}`).join('\n') + '\nassistant:';

  if (INFERENCE_ENGINE === 'ollama') {
    const response = await ollama.chat({
      model: MODEL_NAME,
      messages,
      options: {
        temperature,
        num_predict: max_tokens,
      },
      stream,
    });

    if (stream) {
      reply.raw.setHeader('Content-Type', 'text/event-stream');
      reply.raw.setHeader('Cache-Control', 'no-cache');
      reply.raw.setHeader('Connection', 'keep-alive');

      for await (const part of response) {
        inferenceTokens.inc({ engine: 'ollama', type: 'chat' }, (part?.message?.content || '').split(' ').length || 0);
        reply.raw.write(`data: ${JSON.stringify({
          choices: [{
            delta: { content: part.message.content },
            index: 0,
          }],
        })}\n\n`);
      }
      reply.raw.write('data: [DONE]\n\n');
      reply.raw.end();
    } else {
      inferenceTokens.inc({ engine: 'ollama', type: 'chat' }, (prompt.split(' ').length || 0));
      return {
        id: `chatcmpl-${Date.now()}`,
        object: 'chat.completion',
        created: Math.floor(Date.now() / 1000),
        model: MODEL_NAME,
        choices: [{
          index: 0,
          message: {
            role: 'assistant',
            content: response.message.content,
          },
          finish_reason: 'stop',
        }],
        usage: {
          prompt_tokens: prompt.split(' ').length,
          completion_tokens: response.message.content.split(' ').length,
          total_tokens: prompt.split(' ').length + response.message.content.split(' ').length,
        },
      };
    }
  } else {
    // vLLM使用
    const completion = await vllm.chat.completions.create({
      model: MODEL_NAME,
      messages,
      max_tokens,
      temperature,
      stream,
    });
    inferenceTokens.inc({ engine: 'vllm', type: 'chat' }, (prompt.split(' ').length || 0));
    return completion;
  }
});

// 自然言語解析エンドポイント（Shodo特化）
fastify.post('/v1/analyze', async (request, reply) => {
  const { text, context = {} } = request.body;

  const systemPrompt = `あなたは日本語の自然言語を解析し、ユーザーの意図を理解するAIアシスタントです。\n以下の形式でJSONを返してください：\n{\n  "intent": "操作の意図",\n  "confidence": 0.0-1.0の確信度,\n  "entities": { 抽出されたエンティティ },\n  "service": "対象サービス（shopify/gmail/stripe等）",\n  "suggestions": ["曖昧な場合の明確化質問"]\n}`;

  const userPrompt = `ユーザー入力: ${text}\nコンテキスト: ${JSON.stringify(context)}`;

  try {
    let response;
    if (INFERENCE_ENGINE === 'ollama') {
      response = await ollama.generate({
        model: MODEL_NAME,
        prompt: `${systemPrompt}\n\n${userPrompt}`,
        format: 'json',
        options: {
          temperature: 0.3,
          num_predict: 1024,
        },
      });
      inferenceTokens.inc({ engine: 'ollama', type: 'analyze' }, (String(text || '').split(' ').length || 0));
      return JSON.parse(response.response);
    } else {
      const completion = await vllm.completions.create({
        model: MODEL_NAME,
        prompt: `${systemPrompt}\n\n${userPrompt}`,
        max_tokens: 1024,
        temperature: 0.3,
      });
      inferenceTokens.inc({ engine: 'vllm', type: 'analyze' }, (String(text || '').split(' ').length || 0));
      return JSON.parse(completion.choices[0].text);
    }
  } catch (error) {
    fastify.log.error(error);
    return {
      intent: 'unknown',
      confidence: 0.0,
      entities: {},
      service: null,
      suggestions: ['もう少し詳しく教えてください'],
      error: error.message,
    };
  }
});

// エンベディング生成
fastify.post('/v1/embeddings', async (request, reply) => {
  const { input, model = 'nomic-embed-text' } = request.body;

  if (INFERENCE_ENGINE === 'ollama') {
    const response = await ollama.embeddings({
      model,
      prompt: input,
    });
    inferenceTokens.inc({ engine: 'ollama', type: 'embeddings' }, (String(input || '').split(' ').length || 0));
    return {
      object: 'list',
      data: [{
        object: 'embedding',
        embedding: response.embedding,
        index: 0,
      }],
      model,
      usage: {
        prompt_tokens: input.split(' ').length,
        total_tokens: input.split(' ').length,
      },
    };
  } else {
    reply.code(501).send({ error: 'Embeddings not supported with vLLM' });
  }
});

// サーバー起動
const start = async () => {
  try {
    const port = process.env.PORT || 8001;
    await fastify.listen({ port, host: '0.0.0.0' });
    
    console.log(`
╔════════════════════════════════════════╗
║     Shodo AI Server Started            ║
╠════════════════════════════════════════╣
║ Engine: ${INFERENCE_ENGINE.padEnd(31)}║
║ Model:  ${MODEL_NAME.padEnd(31)}║
║ Port:   ${String(port).padEnd(31)}║
║ URL:    http://localhost:${port}         ║
╚════════════════════════════════════════╝
    `);

    // Ollamaの場合、モデルの存在確認
    if (INFERENCE_ENGINE === 'ollama') {
      try {
        await ollama.show({ model: MODEL_NAME });
        fastify.log.info(`Model ${MODEL_NAME} is ready`);
      } catch (error) {
        fastify.log.warn(`Model ${MODEL_NAME} not found. Pulling...`);
        await ollama.pull({ model: MODEL_NAME });
        fastify.log.info(`Model ${MODEL_NAME} pulled successfully`);
      }
    }
  } catch (err) {
    fastify.log.error(err);
    process.exit(1);
  }
};

start();