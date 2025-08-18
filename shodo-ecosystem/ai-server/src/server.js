import Fastify from 'fastify';
import cors from '@fastify/cors';
import { Ollama } from 'ollama';
import OpenAI from 'openai';
import dotenv from 'dotenv';

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

// CORS設定
await fastify.register(cors, {
  origin: true,
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
        reply.raw.write(`data: ${JSON.stringify({
          choices: [{ text: part.response, index: 0 }],
        })}\n\n`);
      }
      reply.raw.end();
    } else {
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
    return completion;
  }
});

// 自然言語解析エンドポイント（Shodo特化）
fastify.post('/v1/analyze', async (request, reply) => {
  const { text, context = {} } = request.body;

  const systemPrompt = `あなたは日本語の自然言語を解析し、ユーザーの意図を理解するAIアシスタントです。
以下の形式でJSONを返してください：
{
  "intent": "操作の意図",
  "confidence": 0.0-1.0の確信度,
  "entities": { 抽出されたエンティティ },
  "service": "対象サービス（shopify/gmail/stripe等）",
  "suggestions": ["曖昧な場合の明確化質問"]
}`;

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
      return JSON.parse(response.response);
    } else {
      const completion = await vllm.completions.create({
        model: MODEL_NAME,
        prompt: `${systemPrompt}\n\n${userPrompt}`,
        max_tokens: 1024,
        temperature: 0.3,
      });
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