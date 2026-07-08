"""
Multi-Provider Failover Manager

Provides automatic provider switching when rate limits are hit.
When a provider returns 429/503 (rate limit), the system automatically
switches to the next available provider.

Usage:
    The multi_provider_manager is automatically used by the agent.
    Add multiple providers through the UI or by setting env vars.

Environment Variables:
    MULTIPLE_API_KEYS: Comma-separated list of API keys
    MULTIPLE_MODELS: Comma-separated list of models (same length as API keys)
    MULTIPLE_BASE_URLS: Comma-separated list of base URLs (optional)
"""
