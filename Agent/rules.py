"""
Rules System - File-driven project rules.
Equivalent to Cline's .clinerules file-driven automation.
"""

from pathlib import Path
from typing import List, Optional


class ProjectRules:
    '''
    Manages project-level rules loaded from files.
    Supports .clinerules-style configuration files.
    
    File discovery order:
    1. .clinerules (current directory)
    2. .allama/rules (project rules directory)
    3. ~/.allama/rules.d/*.md (user rules)
    '''
    
    RULE_FILES = [".clinerules", ".allama/rules", "rules.md", "AGENTS.md"]
    
    def __init__(self, workspace_dir: Path):
        self._workspace_dir = workspace_dir
        self._rules: List[str] = []
        self._loaded = False
    
    def load(self) -> List[str]:
        '''Load rules from all discovered rule files.'''
        if self._loaded:
            return self._rules
        
        self._rules = []
        
        # Load project-level rules
        for rule_file in self.RULE_FILES:
            rule_path = self._workspace_dir / rule_file
            if rule_path.exists():
                content = rule_path.read_text(encoding="utf-8", errors="replace")
                if content.strip():
                    self._rules.append(f"# Rules from {rule_file}\n{content}")
        
        # Load user-level rules
        user_rules_dir = Path.home() / ".allama" / "rules.d"
        if user_rules_dir.exists():
            for rule_file in sorted(user_rules_dir.glob("*.md")):
                content = rule_file.read_text(encoding="utf-8", errors="replace")
                if content.strip():
                    self._rules.append(f"# User rule: {rule_file.name}\n{content}")
        
        self._loaded = True
        return self._rules
    
    def get_rules_text(self) -> str:
        '''Get all loaded rules as a single text block.'''
        if not self._rules:
            self.load()
        return "\n\n".join(self._rules)
    
    def add_rule(self, rule: str) -> None:
        '''Add a rule dynamically.'''
        self._rules.append(rule)
    
    def clear_rules(self) -> None:
        '''Clear all loaded rules.'''
        self._rules = []
        self._loaded = False
    
    @property
    def has_rules(self) -> bool:
        if not self._loaded:
            self.load()
        return len(self._rules) > 0


class RuleLoader:
    '''
    Watches for rule file changes and triggers reload.
    '''
    
    def __init__(self, rules: ProjectRules, callback=None):
        self._rules = rules
        self._callback = callback
        self._watched_files = set()
    
    def check_for_changes(self) -> bool:
        '''Check if any rule files have changed.'''
        new_files = set()
        workspace = self._rules._workspace_dir
        
        for rule_file in ProjectRules.RULE_FILES:
            path = workspace / rule_file
            if path.exists():
                new_files.add(str(path.resolve()))
        
        changed = new_files != self._watched_files
        self._watched_files = new_files
        
        if changed and self._callback:
            self._callback()
        
        return changed
