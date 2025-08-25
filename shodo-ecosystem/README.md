# Shodo Ecosystem

**Shodo Ecosystem is a powerful natural language processing platform that enables non-technical users to safely operate SaaS applications through Japanese natural language commands. Unlike traditional automation tools, it combines rule-based analysis with AI-powered understanding to deliver enterprise-grade security while maintaining exceptional performance.**

Shodo provides essential dual-path analysis capabilities that process natural language inputs through both high-speed rule engines and sophisticated AI models, achieving optimal accuracy while maintaining sub-second response times. When deployed in production environments, these tools dramatically reduce operational costs while enhancing security posture.

Shodo is free & open-source, providing enterprise-level capabilities without the premium pricing of commercial alternatives.

You can think of Shodo as an intelligent middleware layer between human operators and complex SaaS ecosystems. With it, users no longer need to navigate complex interfaces, remember API endpoints, or understand technical documentation. Instead, they can use natural language commands like "Export this month's Shopify orders" or "Check Gmail for unread messages."

## Users' Feedback

Most users report that Shodo has transformative effects on their operational efficiency, with many describing it as a game changer for their business processes. Organizations frequently see 97.5% cost reductions and 15x performance improvements when migrating from traditional automation solutions.

However, in very simple workflows or single-service operations, you may not benefit from Shodo's full capabilities. For example, if you only need basic data exports, simpler tools might suffice. You can adjust Shodo to your specific needs using its extensive configuration options.

Several case studies and technical analyses have been published about Shodo:

**Enterprise Deployments:**
- Fortune 500 E-commerce Platform Migration
- Mid-market SaaS Integration Success Stories
- Government Agency Digital Transformation

**Technical Deep Dives:**
- Dual-Path Analysis Architecture
- LPR Security Implementation
- Performance Optimization Strategies

## Demonstration 1 - Efficient Natural Language Processing

A demonstration of Shodo efficiently processing complex natural language queries and routing them to appropriate SaaS services, thereby saving time and reducing errors. Efficient operations are not only useful for cost savings, but also for improving overall system reliability. This effect becomes particularly pronounced in large-scale enterprise deployments.

## Demonstration 2 - Enterprise Security Features

A demonstration of Shodo's LPR (Limited Proxy Rights) system implementing hardware-based authentication and device fingerprinting. Note how Shodo's security features enable organizations to maintain complete audit trails while ensuring zero data leakage.

Shodo is under active development! See the latest updates, upcoming features, and lessons learned to stay up to date.

[Changelog](CHANGELOG.md) | [Roadmap](ROADMAP.md) | [Release Notes](RELEASE_NOTES.md)

## LLM Integration

Shodo provides the necessary infrastructure for natural language workflows, but requires AI models for actual language understanding and generation.

For example, supercharge your SaaS automation with enterprise-grade natural language processing.

Shodo can be integrated with AI models in several ways:

**Direct Integration:**
- OpenAI GPT models for production workloads
- Local models via Ollama for development
- vLLM for high-performance inference
- Custom model endpoints

**Enterprise Features:**
- Model switching and fallback strategies
- Token usage optimization
- Response caching and acceleration
- Multi-model ensemble processing

## Programming Language Support & Integration Capabilities

Shodo's integration capabilities build on modern API standards and service discovery protocols. The platform provides versatile service querying and automation functionalities based on semantic understanding of user intent. Equipped with these capabilities, Shodo discovers and orchestrates services just like an experienced operator would. Shodo can efficiently handle complex workflows even in large enterprise environments with hundreds of integrated services.

Service connectors provide support for a wide range of SaaS platforms. With Shodo, we provide:

**Direct, out-of-the-box support for:**
- Shopify (e-commerce operations)
- Stripe (payment processing)
- Gmail (email automation)
- Slack (communication workflows)
- Universal connector (REST API services)

**Indirect support (may require configuration):**
- Salesforce (CRM operations)
- HubSpot (marketing automation)
- Zendesk (customer support)
- Custom API endpoints

These services are supported through our connector framework, and we continuously test integration reliability across different service versions.

Further services can be easily supported by implementing lightweight adapters for new API specifications.

## Table of Contents

- [Quick Start](#quick-start)
- [Running Shodo Ecosystem](#running-shodo-ecosystem)
- [Usage](#usage)
- [Docker Deployment](#docker-deployment)
- [Production Mode](#production-mode)
- [Configuration](#configuration)
- [Service Integration](#service-integration)
- [Development Environment](#development-environment)
- [Monitoring and Observability](#monitoring-and-observability)
- [Security Features](#security-features)
- [Performance Optimization](#performance-optimization)
- [Troubleshooting](#troubleshooting)
- [Enterprise Support](#enterprise-support)

## Quick Start

Shodo can be deployed in various configurations depending on your requirements.

**For development and testing**, we recommend using Docker Compose with the provided development configuration.
**For production deployments**, use the optimized production configuration with monitoring enabled.
**For enterprise environments**, contact our team for custom deployment strategies.

You will need Docker and Docker Compose installed on your system.

## Running Shodo Ecosystem

You have several options for running Shodo, which are explained in the subsections below.

### Usage

The typical deployment involves running the complete stack using Docker Compose, which orchestrates all required services including the backend API, frontend interface, AI processing server, and supporting infrastructure.

Note that Shodo includes a comprehensive monitoring dashboard by default that displays system metrics and allows for operational oversight. This and other settings can be adjusted in the configuration files.

### Docker Deployment

Docker Compose can be used to run the complete Shodo ecosystem with all dependencies.

```bash
# Clone and setup
git clone https://github.com/your-org/shodo-ecosystem
cd shodo-ecosystem
cp .env.example .env

# Generate SSL certificates for development
./scripts/generate-ssl.sh

# Start the complete stack
docker-compose up -d
```

Explore the configuration options that Shodo provides through environment variables and configuration files.

### Local Development

For development work on Shodo itself:

```bash
# Clone the repository
git clone https://github.com/your-org/shodo-ecosystem
cd shodo-ecosystem

# Edit configuration if needed
cp .env.example .env
# Edit .env with your preferred settings

# Initialize the development environment
make setup

# Start development services with hot reload
make dev
```

When running in development mode, all services will automatically reload when source code changes are detected.

### Production Mode

**Warning:** Production deployment requires careful configuration of security settings, SSL certificates, and environment variables. Please read the production deployment guide before proceeding.

You can run Shodo in production mode with optimized settings:

```bash
# Use production configuration
docker-compose -f docker-compose.production.yml up -d

# Initialize database
docker-compose exec backend python scripts/init_db.py

# Verify deployment
./scripts/health-check.sh
```

The production configuration provides:
- Optimized resource allocation
- Enhanced security settings
- Comprehensive monitoring
- Automatic SSL/TLS termination

## Configuration

Shodo is highly configurable to meet diverse enterprise requirements. While default configurations work for most users, you can fully customize the system by editing configuration files.

Shodo is configured in several layers:

1. **Environment Variables** (`.env` file) for deployment-specific settings
2. **Service Configuration** (`config/` directory) for component-specific settings  
3. **Project Configuration** (`.shodo/` directory) for workspace-specific settings
4. **Runtime Configuration** through API endpoints for dynamic adjustments

### Environment Configuration

The `.env` file contains deployment-wide settings:

```bash
# Core Settings
ENVIRONMENT=production
DEBUG=false
LOG_LEVEL=info

# Security Settings (MUST change in production)
JWT_SECRET_KEY=your-secure-jwt-key-here
ENCRYPTION_KEY=your-encryption-key-here

# AI Configuration
INFERENCE_ENGINE=vllm
MODEL_NAME=openai/gpt-oss-20b
VLLM_URL=http://ai-server:8001

# Database Settings
DATABASE_URL=postgresql+asyncpg://user:pass@postgres:5432/shodo
REDIS_URL=redis://redis:6379
```

### Service Integration

Services are configured through the admin interface or configuration files. Each service requires:

- Authentication credentials
- API endpoint configuration
- Rate limiting settings
- Security policies

Example Shopify configuration:
```yaml
shopify:
  store_url: "your-store.myshopify.com"
  api_key: "${SHOPIFY_API_KEY}"
  api_secret: "${SHOPIFY_API_SECRET}"
  api_version: "2023-10"
  rate_limit: 40  # requests per second
  timeout: 30     # seconds
```

After initial setup, continue with the deployment section that matches your intended use case.

## Service Integration & Configuration

If you primarily work with specific SaaS services, you can configure them at startup by setting service credentials in your environment configuration. This is especially useful for enterprise deployments where service configurations are managed centrally.

Otherwise, services can be configured through the web interface by providing:

**"Configure Shopify integration"**
**"Add Stripe payment processing"**
**"Enable Gmail automation"**

All configured services are automatically validated and monitored. For each service, health checks verify connectivity and credential validity.

**Note:** For production deployments, we recommend pre-configuring all required services to minimize runtime configuration requirements. To do so, run the configuration validation from your deployment directory:

```bash
./scripts/validate-config.sh
```

## Development Environment

### Backend Development

The backend is built with FastAPI and provides:

- RESTful API endpoints
- WebSocket support for real-time updates
- Comprehensive OpenAPI documentation
- Integrated security middleware

```bash
# Backend development
cd backend
python -m venv venv
source venv/bin/activate  # or venv\Scripts\activate on Windows
pip install -r requirements.txt

# Run development server
uvicorn src.main:app --reload --host 0.0.0.0 --port 8000
```

### Frontend Development

The frontend is built with React and TypeScript:

```bash
# Frontend development
cd frontend
npm install

# Start development server
npm start
```

### AI Server Development

The AI server supports multiple inference engines:

```bash
# AI server development
cd ai-server

# For Node.js version (Ollama/OpenAI compatible)
npm install
npm run dev

# For Python version (vLLM)
pip install -r requirements.txt
python src/vllm_server.py
```

## Monitoring and Observability

Shodo includes comprehensive monitoring capabilities:

### Metrics Collection

- **Prometheus**: Time-series metrics collection
- **Grafana**: Visualization and alerting
- **Custom dashboards**: Business and technical metrics

```bash
# Start monitoring stack
docker-compose -f docker-compose.monitoring.yml up -d

# Access dashboards
echo "Grafana: http://localhost:3001"
echo "Prometheus: http://localhost:9090"
```

### Health Monitoring

Comprehensive health checks monitor:

- Service availability and response times
- Database connectivity and performance
- AI model availability and inference speed
- External service integration status

```bash
# Run comprehensive health check
./scripts/health-check.sh

# Quick health status
curl http://localhost/health
```

### Logging

Structured logging provides:

- Request/response tracing
- Performance metrics
- Security event logging
- Error tracking and aggregation

## Security Features

### Environment Behavior Differences (LPR/Rate Limiting)
- **Development**:
  - `main_unified.py` では LPR 強制や厳格なレート制限を簡略化し、開発体験を優先
  - `CORS`/`TrustedHost` はワイルドカード許容
- **Production**:
  - `main_production.py` では `LPREnforcerMiddleware`/`RateLimitMiddleware` を有効化し、最小権限・スコープ検証・監査を必須化
  - `CORS`/`TrustedHost` ワイルドカードは禁止、`CSRF_COOKIE_SECURE=true` 必須
  - Redis が利用不可の場合のレート制限フォールバックは `RATE_LIMIT_FAIL_OPEN` に従う（既定は Fail-Close 推奨）

### AI Server Hardening
- AI サーバ（`ai-server/src/vllm_server.py`）は、以下の保護を実装:
  - CORS は許可リストのみ（`AI_CORS_ORIGINS`）
  - 内部API（`/v1/*`）は `X-Internal-Token` による検証（`AI_INTERNAL_TOKEN` を設定）
  - `/health` `/metrics` `/v1/models` は監視/可観測性向けに公開
- バックエンド→AI サーバ呼び出しは `AI_INTERNAL_TOKEN` を自動付与（`DualPathEngine`）

### LPR (Limited Proxy Rights) System

Shodo implements a novel security architecture:

- **Hardware Authentication**: TPM 2.0 integration for device verification
- **Device Fingerprinting**: Unique device identification
- **Scope Minimization**: Least-privilege access controls
- **Complete Audit Trail**: All operations logged and signed

### Multi-Layer Security

- **Rate Limiting**: Configurable per-endpoint limits
- **Input Validation**: Comprehensive sanitization
- **Encryption**: AES-256 for data at rest, TLS 1.3 for transit
- **Security Headers**: CSRF, XSS, and clickjacking protection

### Compliance

Shodo supports compliance with:

- **GDPR**: European data protection regulations
- **SOC 2 Type II**: Security and availability controls
- **ISO 27001**: Information security management

## Performance Optimization

### Caching Strategy

Multi-layer caching provides optimal performance:

```python
# NLP analysis caching
cache_config = {
    "ttl": 300,        # 5 minutes
    "max_size": 1000,  # LRU eviction
    "compression": True # Memory optimization
}
```

### Database Optimization

- **Connection pooling**: Optimized for concurrent access
- **Query optimization**: Indexed for common access patterns
- **Read replicas**: Support for read-heavy workloads

### AI Model Optimization

- **Model quantization**: Reduced memory footprint
- **Batch processing**: Improved throughput
- **Response caching**: Reduced inference costs

## Troubleshooting

### Common Issues

**Service Startup Failures**
```bash
# Check service logs
docker-compose logs backend

# Verify configuration
./scripts/validate-config.sh

# Reset environment
docker-compose down -v && docker-compose up -d
```

**AI Model Connection Issues**
```bash
# Test AI server connectivity
curl http://localhost:8001/health

# Check model availability
docker-compose exec ai-server ollama list  # For Ollama
```

**Database Connection Problems**
```bash
# Test database connectivity
docker-compose exec postgres psql -U shodo -d shodo -c "SELECT 1;"

# Initialize database if needed
docker-compose exec backend python scripts/init_db.py
```

### Performance Issues

For performance optimization:

1. **Monitor resource usage**: Use the monitoring dashboard
2. **Analyze slow queries**: Check database performance metrics
3. **Review cache hit rates**: Optimize caching strategies
4. **Scale services**: Add replicas for high-load components

### Log Analysis

Comprehensive logging helps diagnose issues:

```bash
# View recent logs
docker-compose logs --tail=100 -f

# Search for errors
docker-compose logs | grep ERROR

# Analyze performance
./scripts/analyze-performance.sh
```

## Enterprise Support

### Professional Services

- **Implementation consulting**: Architecture and deployment guidance
- **Custom development**: Tailored features and integrations
- **Training programs**: Team onboarding and best practices
- **24/7 support**: Production environment assistance

### Deployment Options

- **On-premises**: Complete control and data sovereignty
- **Cloud deployment**: Managed infrastructure options
- **Hybrid configurations**: Mix of on-premises and cloud services
- **Multi-region**: Global deployment strategies

### SLA and Support Tiers

- **Community**: GitHub issues and documentation
- **Professional**: Email support with SLA
- **Enterprise**: Dedicated support team and custom SLA

## Comparison with Other Automation Platforms

### Subscription-Based Platforms

Many commercial automation platforms require expensive subscriptions and lock you into their ecosystems. Shodo provides comparable functionality while:

- **Maintaining data sovereignty**: All processing occurs on your infrastructure
- **Avoiding vendor lock-in**: Open-source architecture allows customization
- **Reducing costs**: No per-transaction or per-user fees
- **Ensuring security**: No external data transmission required

### API-Based Solutions

Traditional API integration requires technical expertise and ongoing maintenance. Shodo differs by:

- **Natural language interface**: No technical knowledge required
- **Intelligent routing**: Automatic service selection and orchestration  
- **Error handling**: Robust retry and fallback mechanisms
- **Unified interface**: Single interface for multiple services

### Custom Development

Building custom automation solutions requires significant development resources. Shodo provides:

- **Pre-built connectors**: Immediate integration with popular services
- **Extensible architecture**: Easy addition of new services
- **Proven reliability**: Battle-tested in production environments
- **Ongoing maintenance**: Regular updates and security patches

## Acknowledgements

Shodo Ecosystem builds upon several excellent open-source projects:

- **FastAPI**: High-performance Python web framework
- **React**: User interface library
- **PostgreSQL**: Robust relational database
- **Redis**: High-performance caching
- **Docker**: Containerization platform
- **Prometheus & Grafana**: Monitoring and observability

Without these foundational technologies, Shodo would not have been possible.

## Extending Shodo

Shodo is designed for extensibility. You can:

### Add New Service Connectors

Implement new service integrations by extending the base connector class:

```python
from shodo.connectors.base import BaseConnector

class CustomServiceConnector(BaseConnector):
    def authenticate(self, credentials):
        # Implementation here
        pass
    
    def execute_action(self, action, parameters):
        # Implementation here
        pass
```

### Customize NLP Processing

Extend the dual-path analysis engine:

```python
from shodo.nlp.base import BaseAnalyzer

class CustomAnalyzer(BaseAnalyzer):
    def analyze(self, text, context):
        # Custom analysis logic
        pass
```

### Add Monitoring Metrics

Implement custom metrics collection:

```python
from shodo.monitoring.base import BaseMetric

class CustomMetric(BaseMetric):
    def collect(self):
        # Metric collection logic
        pass
```

For detailed extension documentation, see the [Developer Guide](docs/developer-guide.md).

## License

Shodo Ecosystem is released under the MIT License. See [LICENSE](LICENSE) for details.

## Contributing

We welcome contributions! Please see our [Contributing Guidelines](CONTRIBUTING.md) for details on:

- Code style and standards
- Testing requirements
- Pull request process
- Community guidelines

## Support

- **Documentation**: [docs.shodo-ecosystem.com](https://docs.shodo-ecosystem.com)
- **Community**: [GitHub Discussions](https://github.com/your-org/shodo-ecosystem/discussions)
- **Issues**: [GitHub Issues](https://github.com/your-org/shodo-ecosystem/issues)
- **Enterprise**: [Contact Sales](mailto:enterprise@shodo-ecosystem.com)