import os
import time
import json
import hashlib
import re
from groq import Groq, APIError
from pathlib import Path

class LLMClientManager:
    _instance = None
    
    @classmethod
    def get_instance(cls, working_dir=None):
        if cls._instance is None:
            cls._instance = cls(working_dir)
        return cls._instance
    
    def _read_api_key(self):
        """Read Groq API key from file."""
        key_path = Path.home() / '.mingdaoai' / 'groq.key'
        try:
            if not key_path.exists():
                raise ValueError(f"Groq API key file not found at {key_path}")
            return key_path.read_text().strip()
        except Exception as e:
            raise ValueError(f"Failed to read Groq API key: {str(e)}")
    
    def __init__(self, working_dir=None):
        if LLMClientManager._instance is not None:
            raise Exception("LLMClientManager is a singleton! Use get_instance() instead.")
            
        if working_dir is None:
            raise ValueError("working_dir must be provided")
            
        self.model = "deepseek-r1-distill-llama-70b"
        # Set cache and debug directories within working directory
        self.cache_dir = os.path.join(working_dir, 'cache', 'llm')
        os.makedirs(self.cache_dir, exist_ok=True)
        self.debug_dir = os.path.join(working_dir, 'debug', 'llm')
        os.makedirs(self.debug_dir, exist_ok=True)
        
        # Initialize Groq client with API key from file
        api_key = self._read_api_key()
        self.client = Groq(api_key=api_key)
        
        LLMClientManager._instance = self
        
    def _clean_response(self, response):
        """Clean the response by removing <think> blocks and unescaping JSON."""
        # Remove <think>...</think> blocks, handling multiline content
        response = re.sub(r'<think>[\s\S]*?</think>', '', response)
        
        # If response contains ```json ... ``` block, extract just the JSON
        json_match = re.search(r'```json\s*([\s\S]*?)\s*```', response)
        if json_match:
            response = json_match.group(1)
        
        # Remove any remaining markdown code block markers
        response = re.sub(r'```\w*\s*|\s*```', '', response)
        
        return response.strip()
        
    def create_chat_completion(self, system_prompt, user_prompt, max_tokens=8000):
        """Create a chat completion with caching"""
        # Generate a hash key for caching
        cache_key = hashlib.md5((system_prompt + user_prompt).encode('utf-8')).hexdigest()
        cache_file = os.path.join(self.cache_dir, f"chat_completion_cache_{cache_key}.txt")
        
        # Log input prompts
        debug_file = os.path.join(self.debug_dir, f"debug_{int(time.time())}_{cache_key[:8]}.json")
        debug_data = {
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "system_prompt": system_prompt,
            "user_prompt": user_prompt,
            "max_tokens": max_tokens
        }
        
        # Debug the input messages regardless of cache/API
        print("\nDebugging input messages:")
        print(f"System prompt snippet: {system_prompt[:100]}..." if len(system_prompt) > 100 else f"System prompt: {system_prompt}")
        print(f"User prompt snippet: {user_prompt[:100]}..." if len(user_prompt) > 100 else f"User prompt: {user_prompt}")
        
        # Check if cached result exists and is fresh
        if os.path.exists(cache_file):
            cache_age = time.time() - os.path.getmtime(cache_file)
            if cache_age < 86400:  # 1 day in seconds
                with open(cache_file, 'r', encoding='utf-8') as f:
                    cached_response = f.read()
                    print("\nUsing cached chat completion")
                    print(f"Cache age: {int(cache_age/60)} minutes")
                    # Clean the cached response
                    cached_response = self._clean_response(cached_response)
                    print(f"Debug: Cached response snippet: {cached_response[:100]}...")
                    debug_data["response"] = cached_response
                    debug_data["source"] = "cache"
                    with open(debug_file, 'w', encoding='utf-8') as df:
                        json.dump(debug_data, df, indent=2)
                    return cached_response
        
        # If no fresh cache, perform API call to Groq with retries
        max_retries = 3
        retry_delay = 3  # seconds
        attempt = 0
        
        while attempt < max_retries:
            try:
                print(f"\nMaking API call to Groq with model: {self.model}")
                messages = [
                    {
                        'role': 'system',
                        'content': system_prompt
                    },
                    {
                        'role': 'user',
                        'content': user_prompt
                    }
                ]
                
                print("\nStreaming response:")
                stream = self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    max_tokens=max_tokens,
                    stream=True
                )
                
                # Collect the full response while streaming
                full_response = ""
                for chunk in stream:
                    if chunk.choices[0].delta.content is not None:
                        chunk_content = chunk.choices[0].delta.content
                        full_response += chunk_content
                
                # Print a snippet of the response
                print(f"Response snippet: {full_response[:100]}..." if len(full_response) > 100 else f"Response: {full_response}")
                print("\n")  # Add newline after streaming completes
                
                # Clean the response
                raw_text = self._clean_response(full_response)
                print(f"\nDebug: Complete response received. Length: {len(raw_text)} characters")
                
                # Cache the response
                with open(cache_file, 'w', encoding='utf-8') as f:
                    f.write(raw_text)
                
                # Save debug info
                debug_data["response"] = raw_text
                debug_data["source"] = "api"
                with open(debug_file, 'w', encoding='utf-8') as df:
                    json.dump(debug_data, df, indent=2)
                
                return raw_text
                
            except APIError as e:
                attempt += 1
                if attempt < max_retries:
                    print(f"\nGroq API Error (attempt {attempt}/{max_retries}): {str(e)}")
                    time.sleep(retry_delay)
                else:
                    print(f"\nFailed after {max_retries} attempts. Last error: {str(e)}")
                    raise
            except Exception as e:
                print(f"\nUnexpected error: {str(e)}")
                raise
    
    def get_model(self):
        return self.model 