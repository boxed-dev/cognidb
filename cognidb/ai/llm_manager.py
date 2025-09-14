"""LLM manager with multi-provider support and cost tracking."""

import time
from typing import Dict, Any, Optional, List, Union
from abc import ABC, abstractmethod
from dataclasses import dataclass
from ..config.settings import LLMConfig, LLMProvider
from ..core.exceptions import CogniDBError, RateLimitError
from .cost_tracker import CostTracker
from .providers import (
    OpenAIProvider,
    AnthropicProvider,
    AzureOpenAIProvider,
    HuggingFaceProvider,
    LocalProvider
)


@dataclass
class LLMResponse:
    """LLM response container."""
    content: str
    model: str
    provider: str
    usage: Dict[str, int]
    cost: float
    latency: float
    cached: bool = False


class LLMManager:
    """
    Manages LLM interactions with multiple providers.
    
    Features:
    - Multi-provider support with fallback
    - Cost tracking and limits
    - Rate limiting
    - Response caching
    - Token usage tracking
    """
    
    def __init__(self, config: LLMConfig, cache_provider=None):
        """
        Initialize LLM manager.
        
        Args:
            config: LLM configuration
            cache_provider: Optional cache provider for response caching
        """
        self.config = config
        self.cache = cache_provider
        self.cost_tracker = CostTracker(max_daily_cost=config.max_cost_per_day)
        
        # Initialize primary provider
        self.primary_provider = self._create_provider(config.provider, config)
        
        # Initialize fallback providers
        self.fallback_providers = []
        if config.provider != LLMProvider.OPENAI:
            self.fallback_providers.append(
                self._create_provider(LLMProvider.OPENAI, config)
            )
        
        # Rate limiting
        self._request_times: List[float] = []
        self._last_request_time = 0
    
    def generate(self, 
                 prompt: str,
                 system_prompt: Optional[str] = None,
                 max_tokens: Optional[int] = None,
                 temperature: Optional[float] = None,
                 use_cache: bool = True) -> LLMResponse:
        """
        Generate response from LLM.
        
        Args:
            prompt: User prompt
            system_prompt: System prompt (overrides config)
            max_tokens: Maximum tokens (overrides config)
            temperature: Temperature (overrides config)
            use_cache: Whether to use cached responses
            
        Returns:
            LLM response
            
        Raises:
            RateLimitError: If rate limit exceeded
            CogniDBError: If generation fails
        """
        # Check rate limits
        self._check_rate_limit()
        
        # Check cost limits
        if self.cost_tracker.is_limit_exceeded():
            raise CogniDBError("Daily cost limit exceeded")
        
        # Check cache
        if use_cache and self.cache:
            cache_key = self._generate_cache_key(prompt, system_prompt)
            cached_response = self.cache.get(cache_key)
            if cached_response:
                cached_response['cached'] = True
                return LLMResponse(**cached_response)
        
        # Prepare parameters
        params = {
            'prompt': prompt,
            'system_prompt': system_prompt or self.config.system_prompt,
            'max_tokens': max_tokens or self.config.max_tokens,
            'temperature': temperature or self.config.temperature
        }
        
        # Try primary provider
        start_time = time.time()
        response = None
        last_error = None
        
        for provider in [self.primary_provider] + self.fallback_providers:
            try:
                response = provider.generate(**params)
                response['provider'] = provider.name
                response['latency'] = time.time() - start_time
                break
            except Exception as e:
                last_error = e
                continue
        
        if response is None:
            raise CogniDBError(f"All LLM providers failed: {last_error}")
        
        # Track cost
        cost = self._calculate_cost(response['usage'], response['model'])
        response['cost'] = cost
        self.cost_tracker.track_usage(cost, response['usage'])
        
        # Cache response
        if use_cache and self.cache:
            self.cache.set(
                cache_key,
                response,
                ttl=self.config.llm_response_ttl
            )
        
        # Update rate limiting
        self._request_times.append(time.time())
        
        return LLMResponse(**response)
    
    def generate_with_examples(self,
                             prompt: str,
                             examples: List[Dict[str, str]],
                             **kwargs) -> LLMResponse:
        """
        Generate response with few-shot examples.
        
        Args:
            prompt: User prompt
            examples: List of input/output examples
            **kwargs: Additional generation parameters
            
        Returns:
            LLM response
        """
        # Build prompt with examples
        formatted_prompt = self._format_with_examples(prompt, examples)
        return self.generate(formatted_prompt, **kwargs)
    
    def stream_generate(self,
                       prompt: str,
                       callback,
                       **kwargs):
        """
        Stream generation with callback.
        
        Args:
            prompt: User prompt
            callback: Function called with each token
            **kwargs: Additional generation parameters
        """
        if not self.config.enable_streaming:
            raise CogniDBError("Streaming not enabled in configuration")
        
        # Check if provider supports streaming
        if not hasattr(self.primary_provider, 'stream_generate'):
            raise CogniDBError("Provider does not support streaming")
        
        # Stream from provider
        self.primary_provider.stream_generate(prompt, callback, **kwargs)
    
    def get_usage_stats(self) -> Dict[str, Any]:
        """Get usage statistics."""
        return {
            'total_cost': self.cost_tracker.get_total_cost(),
            'daily_cost': self.cost_tracker.get_daily_cost(),
            'token_usage': self.cost_tracker.get_token_usage(),
            'request_count': len(self._request_times),
            'cache_stats': self.cache.get_stats() if self.cache else None
        }
    
    def _create_provider(self, provider_type: LLMProvider, config: LLMConfig):
        """Create LLM provider instance."""
        if provider_type == LLMProvider.OPENAI:
            return OpenAIProvider(config)
        elif provider_type == LLMProvider.ANTHROPIC:
            return AnthropicProvider(config)
        elif provider_type == LLMProvider.AZURE_OPENAI:
            return AzureOpenAIProvider(config)
        elif provider_type == LLMProvider.HUGGINGFACE:
            return HuggingFaceProvider(config)
        elif provider_type == LLMProvider.LOCAL:
            return LocalProvider(config)
        else:
            raise ValueError(f"Unknown provider: {provider_type}")
    
    def _check_rate_limit(self) -> None:
        """Check and enforce rate limits."""
        current_time = time.time()
        
        # Clean old request times
        minute_ago = current_time - 60
        self._request_times = [
            t for t in self._request_times if t > minute_ago
        ]
        
        # Check rate limit
        if len(self._request_times) >= self.config.max_queries_per_minute:
            retry_after = 60 - (current_time - self._request_times[0])
            raise RateLimitError(
                f"Rate limit exceeded ({self.config.max_queries_per_minute}/min)",
                retry_after=int(retry_after)
            )
    
    def _generate_cache_key(self, prompt: str, system_prompt: Optional[str]) -> str:
        """Generate cache key for prompt."""
        import hashlib
        
        key_parts = [
            self.config.provider.value,
            self.config.model_name,
            str(self.config.temperature),
            str(self.config.max_tokens),
            system_prompt or self.config.system_prompt or "",
            prompt
        ]
        
        key_string = "|".join(key_parts)
        return f"llm:{hashlib.sha256(key_string.encode()).hexdigest()}"
    
    def _calculate_cost(self, usage: Dict[str, int], model: str) -> float:
        """Calculate cost based on token usage."""
        # Model pricing (per 1K tokens)
        pricing = {
            # OpenAI
            'gpt-4': {'input': 0.03, 'output': 0.06},
            'gpt-4-turbo': {'input': 0.01, 'output': 0.03},
            'gpt-3.5-turbo': {'input': 0.0005, 'output': 0.0015},
            # Anthropic
            'claude-3-opus': {'input': 0.015, 'output': 0.075},
            'claude-3-sonnet': {'input': 0.003, 'output': 0.015},
            'claude-3-haiku': {'input': 0.00025, 'output': 0.00125},
            # Default
            'default': {'input': 0.001, 'output': 0.002}
        }
        
        model_pricing = pricing.get(model, pricing['default'])
        
        input_cost = (usage.get('prompt_tokens', 0) / 1000) * model_pricing['input']
        output_cost = (usage.get('completion_tokens', 0) / 1000) * model_pricing['output']
        
        return input_cost + output_cost
    
    def _format_with_examples(self, prompt: str, examples: List[Dict[str, str]]) -> str:
        """Format prompt with few-shot examples."""
        formatted_examples = []
        
        for example in examples:
            formatted_examples.append(
                f"Input: {example['input']}\nOutput: {example['output']}"
            )
        
        examples_text = "\n\n".join(formatted_examples)
        
        return f"""Here are some examples:

{examples_text}

Now, for the following input:
Input: {prompt}
Output:"""