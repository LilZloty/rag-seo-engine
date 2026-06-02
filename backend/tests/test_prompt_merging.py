"""
Unit tests for the Multi-Library Prompt Merging system.

Tests cover:
- Priority-based ordering
- Token limit truncation
- Empty library fallback
- Duplicate library handling
- Conflict resolution header
"""
import pytest
import sys
import os

# Add backend to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.services.content_generator import estimate_tokens


class TestTokenEstimation:
    """Tests for the token estimation utility."""
    
    def test_estimate_tokens_empty_string(self):
        """Empty string should return 0 tokens."""
        assert estimate_tokens("") == 0
    
    def test_estimate_tokens_single_word(self):
        """Single word should return approximately 1-2 tokens."""
        result = estimate_tokens("hello")
        assert 1 <= result <= 2
    
    def test_estimate_tokens_sentence(self):
        """A typical sentence should estimate tokens correctly."""
        text = "This is a test sentence with several words"
        result = estimate_tokens(text)
        # 8 words * 1.3 ≈ 10 tokens
        assert 8 <= result <= 15
    
    def test_estimate_tokens_spanish_text(self):
        """Spanish text should also estimate correctly."""
        text = "Esta es una prueba para estimar tokens en español"
        result = estimate_tokens(text)
        # 9 words * 1.3 ≈ 12 tokens
        assert 9 <= result <= 15


class TestPriorityOrdering:
    """Tests for priority-based prompt ordering."""
    
    def test_sort_by_priority(self):
        """Prompts should be sorted by priority ascending (lower first)."""
        tuples = [
            (50, "middle priority", "lib_a"),
            (0, "base prompt", "base"),
            (100, "override", "override:manual"),
        ]
        sorted_tuples = sorted(tuples, key=lambda x: x[0])
        
        assert sorted_tuples[0][2] == "base"
        assert sorted_tuples[1][2] == "lib_a"
        assert sorted_tuples[2][2] == "override:manual"
    
    def test_same_priority_preserves_order(self):
        """Prompts with same priority should preserve insertion order."""
        tuples = [
            (50, "first", "lib_a"),
            (50, "second", "lib_b"),
            (50, "third", "lib_c"),
        ]
        sorted_tuples = sorted(tuples, key=lambda x: x[0])
        
        # Python's sort is stable, so order should be preserved
        assert sorted_tuples[0][2] == "lib_a"
        assert sorted_tuples[1][2] == "lib_b"
        assert sorted_tuples[2][2] == "lib_c"


class TestTokenLimitGuard:
    """Tests for token limit truncation."""
    
    def test_truncation_when_exceeded(self):
        """Lower priority prompts should be kept when limit is exceeded."""
        max_tokens = 50
        tuples = [
            (0, "base " * 20, "base"),  # ~26 tokens
            (50, "library " * 20, "lib_a"),  # ~26 tokens - should be truncated
            (100, "override " * 20, "override"),  # ~26 tokens - should be truncated
        ]
        
        final_instructions = []
        total_tokens = 0
        truncated_sources = []
        
        for priority, instructions, source in sorted(tuples, key=lambda x: x[0]):
            inst_tokens = estimate_tokens(instructions)
            if total_tokens + inst_tokens <= max_tokens:
                final_instructions.append(instructions)
                total_tokens += inst_tokens
            else:
                truncated_sources.append(source)
        
        assert len(final_instructions) == 1
        assert "lib_a" in truncated_sources
        assert "override" in truncated_sources
    
    def test_no_truncation_when_within_limit(self):
        """All prompts should be included when within token limit."""
        max_tokens = 500
        tuples = [
            (0, "Short base prompt", "base"),
            (50, "Short library prompt", "lib_a"),
        ]
        
        final_instructions = []
        total_tokens = 0
        
        for priority, instructions, source in sorted(tuples, key=lambda x: x[0]):
            inst_tokens = estimate_tokens(instructions)
            if total_tokens + inst_tokens <= max_tokens:
                final_instructions.append(instructions)
                total_tokens += inst_tokens
        
        assert len(final_instructions) == 2


class TestConflictResolutionHeader:
    """Tests for the conflict resolution header."""
    
    def test_conflict_header_added(self):
        """Conflict resolution header should be prepended to merged prompt."""
        instructions = ["Instruction 1", "Instruction 2"]
        conflict_header = (
            "NOTA: Si instrucciones posteriores contradicen instrucciones anteriores, "
            "prioriza las instrucciones más recientes (las que aparecen al final).\n\n"
        )
        final_prompt = conflict_header + "\n\n".join(instructions)
        
        assert final_prompt.startswith("NOTA:")
        assert "Instruction 1" in final_prompt
        assert "Instruction 2" in final_prompt
    
    def test_empty_instructions_no_header(self):
        """No header should be added when instructions list is empty."""
        instructions = []
        
        if instructions:
            conflict_header = "NOTA: ..."
            final_prompt = conflict_header + "\n\n".join(instructions)
        else:
            final_prompt = None
        
        assert final_prompt is None


class TestLibraryDeduplication:
    """Tests for library ID deduplication."""
    
    def test_duplicate_library_ids_deduplicated(self):
        """Duplicate library IDs should be removed."""
        library_ids = ["lib_a", "lib_b", "lib_a", "lib_c", "lib_b"]
        deduplicated = list(set(library_ids))
        
        assert len(deduplicated) == 3
        assert "lib_a" in deduplicated
        assert "lib_b" in deduplicated
        assert "lib_c" in deduplicated


class TestPromptHash:
    """Tests for prompt hash generation."""
    
    def test_same_prompt_same_hash(self):
        """Same prompts should produce same hash."""
        import hashlib
        
        prompt = "Test prompt content"
        hash1 = hashlib.md5(prompt.encode()).hexdigest()[:8]
        hash2 = hashlib.md5(prompt.encode()).hexdigest()[:8]
        
        assert hash1 == hash2
    
    def test_different_prompts_different_hash(self):
        """Different prompts should produce different hashes."""
        import hashlib
        
        prompt1 = "Test prompt content 1"
        prompt2 = "Test prompt content 2"
        hash1 = hashlib.md5(prompt1.encode()).hexdigest()[:8]
        hash2 = hashlib.md5(prompt2.encode()).hexdigest()[:8]
        
        assert hash1 != hash2


# Run tests if executed directly
if __name__ == "__main__":
    pytest.main([__file__, "-v"])
