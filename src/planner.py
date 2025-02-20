import os
import json
from .llm_client import LLMClientManager

class ResearchPlanner:
    def __init__(self, working_dir):
        self.llm_manager = LLMClientManager.get_instance(working_dir)
        
    def create_plan(self, research_topic):
        """
        Create a research plan.
        Returns JSON-formatted plan with search queries and strategy.
        """
        prompt = f"""
        Create a research plan for the following topic:
        {research_topic}
        
        Please provide:
        1. A list of specific search queries to find relevant information
        2. Key areas to investigate
        3. Important aspects to look for in the results
        4. Any specific sources or websites to focus on
        
        Format the response as a JSON object with these fields:
        {{
            "search_queries": ["query1", "query2", ...],
            "key_areas": ["area1", "area2", ...],
            "important_aspects": ["aspect1", "aspect2", ...],
            "target_sources": ["source1", "source2", ...]
        }}
        
        Keep queries focused and specific to get the most relevant results. 
        Search queries should be short and concise, no more than 10 words.
        
        Simply return the JSON object. Do not include any other text or comments, or put anything in quotes.
        """
        
        system_prompt = "You are a research planning assistant focused on creating effective search strategies."
        
        response = self.llm_manager.create_chat_completion(
            system_prompt=system_prompt,
            user_prompt=prompt,
            max_tokens=2000
        )
        
        # Parse and validate the response
        assert isinstance(response, str), "Response must be a string"
        try:
            plan = json.loads(response)
            assert 'search_queries' in plan, "Plan must include search queries"
            assert len(plan['search_queries']) > 0, "Plan must have at least one search query"
            for query in plan['search_queries']:
                assert len(query.split()) < 15, f"Search query '{query}' exceeds 15 words"
            return json.dumps(plan, indent=2)
        except json.JSONDecodeError:
            print("Failed to parse response as JSON:", response)
            raise
            
