import os
import time
import json
import hashlib
from ollama import chat
from ollama import ChatResponse

class LLMClientManager:
    _instance = None
    
    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance
    
    def __init__(self):
        if LLMClientManager._instance is not None:
            raise Exception("LLMClientManager is a singleton! Use get_instance() instead.")
            
        self.model = "deepseek-r1:8b"
        self.cache_dir = os.path.join(os.path.dirname(__file__), '..', 'cache', 'llm')
        os.makedirs(self.cache_dir, exist_ok=True)
        # Add debug directory
        self.debug_dir = os.path.join(os.path.dirname(__file__), '..', 'debug', 'llm')
        os.makedirs(self.debug_dir, exist_ok=True)
        LLMClientManager._instance = self
        
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
                    print(f"Debug: Cached response snippet: {cached_response[:100]}...")
                    debug_data["response"] = cached_response
                    debug_data["source"] = "cache"
                    with open(debug_file, 'w', encoding='utf-8') as df:
                        json.dump(debug_data, df, indent=2)
                    return cached_response
        
        # If no fresh cache, perform API call to Ollama
        try:
            print(f"\nMaking API call to Ollama with model: {self.model}")
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
            stream = chat(
                model=self.model,
                messages=messages,
                stream=True,
                options={
                    'num_predict': max_tokens
                }
            )
            
            # Collect the full response while streaming
            full_response = ""
            for chunk in stream:
                chunk_content = chunk['message']['content']
                print(chunk_content, end='', flush=True)
                full_response += chunk_content
            
            print("\n")  # Add newline after streaming completes
            
            raw_text = full_response
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
            
        except Exception as e:
            print(f"\nError in API call: {str(e)}")
            raise
    
    def get_model(self):
        return self.model 