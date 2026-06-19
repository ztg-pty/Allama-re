"""
Context Compaction - Structured message compression strategy.
Equivalent to Cline's context compaction strategy registry in core layer.
"""

from typing import Dict, List, Optional


class CompactionStrategy:
    '''Base class for context compaction strategies.'''
    
    def name(self) -> str:
        raise NotImplementedError
    
    def compress(self, messages: List[Dict[str, str]], **kwargs) -> List[Dict[str, str]]:
        raise NotImplementedError


class KeepLastStrategy(CompactionStrategy):
    '''Keep only the last N messages, discard older ones.'''
    
    def __init__(self, keep_last: int = 6):
        self._keep_last = keep_last
    
    def name(self) -> str:
        return "keep_last"
    
    def compress(self, messages: List[Dict[str, str]], **kwargs) -> List[Dict[str, str]]:
        keep = kwargs.get("keep_last", self._keep_last)
        if len(messages) <= keep:
            return messages
        return messages[-keep:]


class TokenBudgetStrategy(CompactionStrategy):
    '''Compress messages to stay within a token budget.'''
    
    def __init__(self, max_tokens: int = 8192):
        self._max_tokens = max_tokens
    
    def name(self) -> str:
        return "token_budget"
    
    def compress(self, messages: List[Dict[str, str]], **kwargs) -> List[Dict[str, str]]:
        max_tokens = kwargs.get("max_tokens", self._max_tokens)
        
        # Estimate tokens (rough: ~4 chars per token)
        def estimate_tokens(msgs):
            text = "\n".join(m.get("content", "") for m in msgs)
            return max(1, len(text) // 4)
        
        if estimate_tokens(messages) <= max_tokens:
            return messages
        
        # Keep last messages that fit within budget
        result = []
        for msg in reversed(messages):
            test = [msg] + result
            if estimate_tokens(test) <= max_tokens:
                result = test
            else:
                break
        
        return list(reversed(result))


class SummarizeStrategy(CompactionStrategy):
    '''Keep recent messages, summarize older ones.'''
    
    def __init__(self, keep_recent: int = 6, summarize_older: bool = True):
        self._keep_recent = keep_recent
        self._summarize_older = summarize_older
    
    def name(self) -> str:
        return "summarize"
    
    def compress(self, messages: List[Dict[str, str]], **kwargs) -> List[Dict[str, str]]:
        keep = kwargs.get("keep_last", self._keep_recent)
        
        if len(messages) <= keep:
            return messages
        
        recent = messages[-keep:]
        older = messages[:-keep]
        
        if self._summarize_older and older:
            summary = self._summarize_messages(older)
            recent.insert(0, {
                "role": "system",
                "content": f"[Conversation summary of {len(older)} earlier messages]\n{summary}"
            })
        
        return recent
    
    @staticmethod
    def _summarize_messages(messages: List[Dict[str, str]]) -> str:
        '''Create a simple summary from older messages.'''
        user_msgs = [m.get("content", "") for m in messages if m.get("role") == "user"]
        assistant_msgs = [m.get("content", "") for m in messages if m.get("role") == "assistant"]
        
        summary_parts = []
        for i, (q, a) in enumerate(zip(user_msgs, assistant_msgs)):
            q_preview = q[:200] + ("..." if len(q) > 200 else "")
            a_preview = a[:200] + ("..." if len(a) > 200 else "")
            summary_parts.append(f"Q{i+1}: {q_preview}\nA{i+1}: {a_preview}")
        
        return "\n\n".join(summary_parts[:10])  # Limit summary length


# Strategy registry
class CompactionStrategyRegistry:
    '''Registry for context compaction strategies.'''
    
    def __init__(self):
        self._strategies = {}
        self._default = "keep_last"
        self._register_defaults()
    
    def _register_defaults(self):
        self.register(KeepLastStrategy())
        self.register(TokenBudgetStrategy())
        self.register(SummarizeStrategy())
    
    def register(self, strategy: CompactionStrategy):
        self._strategies[strategy.name()] = strategy
    
    def get(self, name: str) -> CompactionStrategy:
        if name in self._strategies:
            return self._strategies[name]
        return self._strategies.get(self._default)
    
    def default(self) -> CompactionStrategy:
        return self._strategies.get(self._default, KeepLastStrategy())
    
    def list_strategies(self) -> List[str]:
        return list(self._strategies.keys())
    
    def compress(self, messages: List[Dict[str, str]], 
                 strategy_name: Optional[str] = None, **kwargs) -> List[Dict[str, str]]:
        '''Compress messages using the specified strategy.'''
        if strategy_name:
            strategy = self.get(strategy_name)
        else:
            strategy = self.default()
        return strategy.compress(messages, **kwargs)
    
    def estimate_tokens(self, messages: List[Dict[str, str]]) -> int:
        '''Estimate token count for messages.'''
        text = "\n".join(m.get("content", "") for m in messages)
        return max(1, len(text) // 4)
