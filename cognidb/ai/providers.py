"""LLM provider implementations."""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, Callable
import time
from ..config.settings import LLMConfig
from ..core.exceptions import CogniDBError


class LLMProvider(ABC):
    """Abstract base class for LLM providers."""
    
    def __init__(self, config: LLMConfig):
        self.config = config
        self.name = self.__class__.__name__
    
    @abstractmethod
    def generate(self, 
                prompt: str,
                system_prompt: Optional[str] = None,
                max_tokens: Optional[int] = None,
                temperature: Optional[float] = None) -> Dict[str, Any]:
        """
        Generate response from LLM.
        
        Returns:
            Dictionary with:
            - content: Generated text
            - model: Model used
            - usage: Token usage statistics
        """
        pass


class OpenAIProvider(LLMProvider):
    """OpenAI provider implementation."""
    
    def __init__(self, config: LLMConfig):
        super().__init__(config)
        self.name = "OpenAI"
        
        try:
            from openai import OpenAI
            self.client = OpenAI(
                api_key=config.api_key,
                timeout=config.timeout,
                max_retries=config.retry_attempts
            )
        except ImportError:
            raise CogniDBError("openai package required. Install with: pip install openai")
    
    def generate(self, 
                prompt: str,
                system_prompt: Optional[str] = None,
                max_tokens: Optional[int] = None,
                temperature: Optional[float] = None) -> Dict[str, Any]:
        """Generate response using OpenAI API."""
        messages = []
        
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        
        messages.append({"role": "user", "content": prompt})
        
        try:
            response = self.client.chat.completions.create(
                model=self.config.model_name,
                messages=messages,
                max_tokens=max_tokens or self.config.max_tokens,
                temperature=temperature or self.config.temperature,
                n=1
            )
            
            return {
                'content': response.choices[0].message.content,
                'model': response.model,
                'usage': {
                    'prompt_tokens': response.usage.prompt_tokens,
                    'completion_tokens': response.usage.completion_tokens,
                    'total_tokens': response.usage.total_tokens
                }
            }
        except Exception as e:
            raise CogniDBError(f"OpenAI API error: {str(e)}")
    
    def stream_generate(self,
                       prompt: str,
                       callback: Callable[[str], None],
                       system_prompt: Optional[str] = None,
                       max_tokens: Optional[int] = None,
                       temperature: Optional[float] = None):
        """Stream generation with OpenAI."""
        messages = []
        
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        
        messages.append({"role": "user", "content": prompt})
        
        try:
            stream = self.client.chat.completions.create(
                model=self.config.model_name,
                messages=messages,
                max_tokens=max_tokens or self.config.max_tokens,
                temperature=temperature or self.config.temperature,
                stream=True
            )
            
            for chunk in stream:
                if chunk.choices[0].delta.content:
                    callback(chunk.choices[0].delta.content)
                    
        except Exception as e:
            raise CogniDBError(f"OpenAI streaming error: {str(e)}")


class AnthropicProvider(LLMProvider):
    """Anthropic Claude provider implementation."""
    
    def __init__(self, config: LLMConfig):
        super().__init__(config)
        self.name = "Anthropic"
        
        try:
            from anthropic import Anthropic
            self.client = Anthropic(
                api_key=config.api_key,
                timeout=config.timeout,
                max_retries=config.retry_attempts
            )
        except ImportError:
            raise CogniDBError("anthropic package required. Install with: pip install anthropic")
    
    def generate(self, 
                prompt: str,
                system_prompt: Optional[str] = None,
                max_tokens: Optional[int] = None,
                temperature: Optional[float] = None) -> Dict[str, Any]:
        """Generate response using Anthropic API."""
        try:
            response = self.client.messages.create(
                model=self.config.model_name,
                system=system_prompt if system_prompt else None,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=max_tokens or self.config.max_tokens,
                temperature=temperature or self.config.temperature
            )
            
            # Extract text content
            content = response.content[0].text if response.content else ""
            
            return {
                'content': content,
                'model': response.model,
                'usage': {
                    'prompt_tokens': response.usage.input_tokens,
                    'completion_tokens': response.usage.output_tokens,
                    'total_tokens': response.usage.input_tokens + response.usage.output_tokens
                }
            }
        except Exception as e:
            raise CogniDBError(f"Anthropic API error: {str(e)}")


class AzureOpenAIProvider(LLMProvider):
    """Azure OpenAI provider implementation."""
    
    def __init__(self, config: LLMConfig):
        super().__init__(config)
        self.name = "AzureOpenAI"
        
        if not config.azure_endpoint or not config.azure_deployment:
            raise CogniDBError("Azure endpoint and deployment required")
        
        try:
            from openai import AzureOpenAI
            self.client = AzureOpenAI(
                api_key=config.api_key,
                api_version="2024-02-01",
                azure_endpoint=config.azure_endpoint,
                timeout=config.timeout,
                max_retries=config.retry_attempts
            )
        except ImportError:
            raise CogniDBError("openai package required. Install with: pip install openai")
    
    def generate(self, 
                prompt: str,
                system_prompt: Optional[str] = None,
                max_tokens: Optional[int] = None,
                temperature: Optional[float] = None) -> Dict[str, Any]:
        """Generate response using Azure OpenAI."""
        messages = []
        
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        
        messages.append({"role": "user", "content": prompt})
        
        try:
            response = self.client.chat.completions.create(
                model=self.config.azure_deployment,
                messages=messages,
                max_tokens=max_tokens or self.config.max_tokens,
                temperature=temperature or self.config.temperature
            )
            
            return {
                'content': response.choices[0].message.content,
                'model': self.config.azure_deployment,
                'usage': {
                    'prompt_tokens': response.usage.prompt_tokens,
                    'completion_tokens': response.usage.completion_tokens,
                    'total_tokens': response.usage.total_tokens
                }
            }
        except Exception as e:
            raise CogniDBError(f"Azure OpenAI API error: {str(e)}")


class HuggingFaceProvider(LLMProvider):
    """HuggingFace provider implementation."""
    
    def __init__(self, config: LLMConfig):
        super().__init__(config)
        self.name = "HuggingFace"
        
        if not config.huggingface_model_id:
            raise CogniDBError("HuggingFace model ID required")
        
        try:
            from transformers import pipeline, AutoTokenizer
            self.tokenizer = AutoTokenizer.from_pretrained(config.huggingface_model_id)
            self.pipeline = pipeline(
                "text-generation",
                model=config.huggingface_model_id,
                tokenizer=self.tokenizer,
                device=0 if self._has_gpu() else -1
            )
        except ImportError:
            raise CogniDBError(
                "transformers package required. Install with: pip install transformers torch"
            )
    
    def generate(self, 
                prompt: str,
                system_prompt: Optional[str] = None,
                max_tokens: Optional[int] = None,
                temperature: Optional[float] = None) -> Dict[str, Any]:
        """Generate response using HuggingFace model."""
        # Combine system prompt and user prompt
        full_prompt = prompt
        if system_prompt:
            full_prompt = f"{system_prompt}\n\n{prompt}"
        
        try:
            # Count input tokens
            input_tokens = len(self.tokenizer.encode(full_prompt))
            
            # Generate
            outputs = self.pipeline(
                full_prompt,
                max_new_tokens=max_tokens or self.config.max_tokens,
                temperature=temperature or self.config.temperature,
                do_sample=True,
                return_full_text=False
            )
            
            generated_text = outputs[0]['generated_text']
            output_tokens = len(self.tokenizer.encode(generated_text))
            
            return {
                'content': generated_text,
                'model': self.config.huggingface_model_id,
                'usage': {
                    'prompt_tokens': input_tokens,
                    'completion_tokens': output_tokens,
                    'total_tokens': input_tokens + output_tokens
                }
            }
        except Exception as e:
            raise CogniDBError(f"HuggingFace generation error: {str(e)}")
    
    def _has_gpu(self) -> bool:
        """Check if GPU is available."""
        try:
            import torch
            return torch.cuda.is_available()
        except ImportError:
            return False


class LocalProvider(LLMProvider):
    """Local model provider implementation."""
    
    def __init__(self, config: LLMConfig):
        super().__init__(config)
        self.name = "Local"
        
        if not config.local_model_path:
            raise CogniDBError("Local model path required")
        
        # Initialize based on model type
        self._init_local_model()
    
    def _init_local_model(self):
        """Initialize local model based on type."""
        model_path = self.config.local_model_path
        
        if model_path.endswith('.gguf') or model_path.endswith('.ggml'):
            # llama.cpp model
            self._init_llamacpp()
        else:
            # Assume HuggingFace model
            self._init_transformers()
    
    def _init_llamacpp(self):
        """Initialize llama.cpp model."""
        try:
            from llama_cpp import Llama
            self.model = Llama(
                model_path=self.config.local_model_path,
                n_ctx=2048,
                n_threads=8
            )
            self.model_type = 'llamacpp'
        except ImportError:
            raise CogniDBError(
                "llama-cpp-python required. Install with: pip install llama-cpp-python"
            )
    
    def _init_transformers(self):
        """Initialize transformers model."""
        try:
            from transformers import AutoModelForCausalLM, AutoTokenizer
            self.tokenizer = AutoTokenizer.from_pretrained(self.config.local_model_path)
            self.model = AutoModelForCausalLM.from_pretrained(
                self.config.local_model_path,
                device_map="auto"
            )
            self.model_type = 'transformers'
        except ImportError:
            raise CogniDBError(
                "transformers package required. Install with: pip install transformers torch"
            )
    
    def generate(self, 
                prompt: str,
                system_prompt: Optional[str] = None,
                max_tokens: Optional[int] = None,
                temperature: Optional[float] = None) -> Dict[str, Any]:
        """Generate response using local model."""
        if self.model_type == 'llamacpp':
            return self._generate_llamacpp(prompt, system_prompt, max_tokens, temperature)
        else:
            return self._generate_transformers(prompt, system_prompt, max_tokens, temperature)
    
    def _generate_llamacpp(self, prompt, system_prompt, max_tokens, temperature):
        """Generate using llama.cpp."""
        full_prompt = prompt
        if system_prompt:
            full_prompt = f"{system_prompt}\n\n{prompt}"
        
        try:
            output = self.model(
                full_prompt,
                max_tokens=max_tokens or self.config.max_tokens,
                temperature=temperature or self.config.temperature,
                stop=["</s>", "\n\n"]
            )
            
            return {
                'content': output['choices'][0]['text'],
                'model': 'local-llamacpp',
                'usage': {
                    'prompt_tokens': output['usage']['prompt_tokens'],
                    'completion_tokens': output['usage']['completion_tokens'],
                    'total_tokens': output['usage']['total_tokens']
                }
            }
        except Exception as e:
            raise CogniDBError(f"Local model generation error: {str(e)}")
    
    def _generate_transformers(self, prompt, system_prompt, max_tokens, temperature):
        """Generate using transformers."""
        full_prompt = prompt
        if system_prompt:
            full_prompt = f"{system_prompt}\n\n{prompt}"
        
        try:
            inputs = self.tokenizer(full_prompt, return_tensors="pt")
            input_tokens = inputs['input_ids'].shape[1]
            
            outputs = self.model.generate(
                inputs['input_ids'],
                max_new_tokens=max_tokens or self.config.max_tokens,
                temperature=temperature or self.config.temperature,
                do_sample=True
            )
            
            generated_text = self.tokenizer.decode(
                outputs[0][inputs['input_ids'].shape[1]:],
                skip_special_tokens=True
            )
            
            output_tokens = outputs[0].shape[0] - input_tokens
            
            return {
                'content': generated_text,
                'model': 'local-transformers',
                'usage': {
                    'prompt_tokens': input_tokens,
                    'completion_tokens': output_tokens,
                    'total_tokens': input_tokens + output_tokens
                }
            }
        except Exception as e:
            raise CogniDBError(f"Local model generation error: {str(e)}")