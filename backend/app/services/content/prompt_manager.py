"""
Prompt Manager - Template Management for Content Generation

Handles prompt templates, versioning, and merging.
"""

import hashlib
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import select

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app.models.library import PromptTemplate, Library, document_library_association
from app.core.logging import get_logger

logger = get_logger(__name__)


@dataclass
class PromptMergeResult:
    """Result of merging prompt templates"""
    merged_prompt: str
    token_count: int
    source_count: int
    truncated: bool
    sources: List[str]
    prompt_hash: str


class PromptMerger:
    """Merges multiple prompt templates with priority-based ordering"""
    
    def __init__(self, max_tokens: int = 4000):
        self.max_tokens = max_tokens
    
    def estimate_tokens(self, text: str) -> int:
        """Estimate token count using word-based heuristic"""
        return int(len(text.split()) * 1.3)
    
    def merge_prompts(
        self,
        prompts: List[Tuple[int, str, str]],
        conflict_header: Optional[str] = None
    ) -> PromptMergeResult:
        """
        Merge multiple prompts with priority ordering.
        
        Args:
            prompts: List of (priority, instructions, source_name) tuples
                     Lower priority = applied first
            conflict_header: Optional header to add for conflict resolution
        
        Returns:
            PromptMergeResult with merged prompt and metadata
        """
        if not prompts:
            return PromptMergeResult(
                merged_prompt="",
                token_count=0,
                source_count=0,
                truncated=False,
                sources=[],
                prompt_hash=""
            )
        
        # Sort by priority (ascending - lower priority = applied first)
        sorted_prompts = sorted(prompts, key=lambda x: x[0])
        
        # Apply token limit guard
        final_prompts = []
        total_tokens = 0
        truncated = False
        sources = []
        
        for priority, instructions, source in sorted_prompts:
            inst_tokens = self.estimate_tokens(instructions)
            if total_tokens + inst_tokens <= self.max_tokens:
                final_prompts.append(instructions)
                total_tokens += inst_tokens
                sources.append(source)
            else:
                truncated = True
                logger.warning(
                    "Prompt truncation occurred",
                    extra={
                        "truncated_source": source,
                        "truncated_priority": priority,
                        "current_tokens": total_tokens,
                        "max_tokens": self.max_tokens
                    }
                )
                break
        
        # Combine with conflict resolution header
        if conflict_header and final_prompts:
            merged_prompt = conflict_header + "\n\n".join(final_prompts)
        elif final_prompts:
            merged_prompt = "\n\n".join(final_prompts)
        else:
            merged_prompt = ""
        
        # Compute prompt hash for tracking
        prompt_hash = hashlib.md5(merged_prompt.encode()).hexdigest()[:8] if merged_prompt else ""
        
        logger.info(
            "Prompt assembly complete",
            extra={
                "prompt_hash": prompt_hash,
                "prompt_tokens": total_tokens,
                "prompt_count": len(final_prompts),
                "truncated": truncated,
                "prompt_sources": sources
            }
        )
        
        return PromptMergeResult(
            merged_prompt=merged_prompt,
            token_count=total_tokens,
            source_count=len(final_prompts),
            truncated=truncated,
            sources=sources,
            prompt_hash=prompt_hash
        )


class PromptTemplateManager:
    """Manages prompt templates in the database"""
    
    def __init__(self, db: Session):
        self.db = db
        self.merger = PromptMerger()
    
    def get_template(self, template_id: str) -> Optional[PromptTemplate]:
        """Get a specific template by ID"""
        return self.db.query(PromptTemplate).filter(
            PromptTemplate.id == template_id
        ).first()
    
    def get_templates_for_libraries(self, library_ids: List[str]) -> List[PromptTemplate]:
        """Get all templates linked to specified libraries"""
        if not library_ids:
            return []
        
        # Deduplicate library IDs
        library_ids = list(set(library_ids))
        
        libs = self.db.query(Library).filter(Library.id.in_(library_ids)).all()
        templates = []
        
        for lib in libs:
            if lib.prompt_template_id:
                tpl = self.get_template(lib.prompt_template_id)
                if tpl:
                    templates.append(tpl)
        
        return templates
    
    def get_prompts_for_libraries(
        self,
        library_ids: List[str],
        include_base: bool = True
    ) -> List[Tuple[int, str, str]]:
        """
        Get all prompt instructions for specified libraries.
        
        Returns:
            List of (priority, instructions, source_name) tuples
        """
        instruction_tuples: List[Tuple[int, str, str]] = []
        
        # Always include base_knowledge library
        if include_base:
            base_lib = self.db.query(Library).filter(
                Library.id == 'base_knowledge'
            ).first()
            if base_lib and base_lib.prompt_template_id:
                base_tpl = self.get_template(base_lib.prompt_template_id)
                if base_tpl:
                    priority = base_tpl.priority if base_tpl.priority is not None else 50
                    instruction_tuples.append((
                        priority,
                        base_tpl.system_instructions,
                        f"base:{base_lib.name}"
                    ))
        
        # Get templates for specified libraries
        templates = self.get_templates_for_libraries(library_ids)
        
        for tpl in templates:
            priority = tpl.priority if tpl.priority is not None else 50
            # Find the library name for this template
            lib = self.db.query(Library).filter(
                Library.prompt_template_id == tpl.id
            ).first()
            lib_name = lib.name if lib else "unknown"
            
            instruction_tuples.append((
                priority,
                tpl.system_instructions,
                f"lib:{lib_name}"
            ))
        
        return instruction_tuples
    
    def merge_for_libraries(
        self,
        library_ids: List[str],
        include_base: bool = True,
        conflict_header: Optional[str] = None
    ) -> PromptMergeResult:
        """
        Merge all prompts for specified libraries.
        
        Args:
            library_ids: List of library IDs to include
            include_base: Whether to include base_knowledge library
            conflict_header: Header for conflict resolution
        
        Returns:
            PromptMergeResult with merged prompt
        """
        instruction_tuples = self.get_prompts_for_libraries(
            library_ids,
            include_base=include_base
        )
        
        return self.merger.merge_prompts(instruction_tuples, conflict_header)
    
    def create_template(
        self,
        name: str,
        system_instructions: str,
        priority: int = 50,
        description: Optional[str] = None
    ) -> PromptTemplate:
        """Create a new prompt template"""
        import uuid
        
        template = PromptTemplate(
            id=str(uuid.uuid4()),
            name=name,
            system_instructions=system_instructions,
            priority=priority,
            description=description
        )
        
        self.db.add(template)
        self.db.commit()
        self.db.refresh(template)
        
        logger.info(
            f"Created prompt template: {name}",
            extra={"template_id": template.id, "priority": priority}
        )
        
        return template
    
    def update_template(
        self,
        template_id: str,
        **kwargs
    ) -> Optional[PromptTemplate]:
        """Update an existing template"""
        template = self.get_template(template_id)
        
        if not template:
            return None
        
        for key, value in kwargs.items():
            if hasattr(template, key):
                setattr(template, key, value)
        
        self.db.commit()
        self.db.refresh(template)
        
        logger.info(f"Updated prompt template: {template.name}")
        
        return template
    
    def delete_template(self, template_id: str) -> bool:
        """Delete a template"""
        template = self.get_template(template_id)
        
        if not template:
            return False
        
        self.db.delete(template)
        self.db.commit()
        
        logger.info(f"Deleted prompt template: {template_id}")
        
        return True
    
    def list_templates(self) -> List[PromptTemplate]:
        """List all templates"""
        return self.db.query(PromptTemplate).all()
    
    def search_templates(self, query: str) -> List[PromptTemplate]:
        """Search templates by name or description"""
        search = f"%{query}%"
        return self.db.query(PromptTemplate).filter(
            (PromptTemplate.name.ilike(search)) |
            (PromptTemplate.description.ilike(search))
        ).all()


# Convenience function
def create_prompt_merger(max_tokens: int = 4000) -> PromptMerger:
    """Create a PromptMerger instance"""
    return PromptMerger(max_tokens=max_tokens)
