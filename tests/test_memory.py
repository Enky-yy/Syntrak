"""Tests for conversation memory management and compaction."""

from campuscli.core.memory import MemoryManager, estimate_tokens


def test_estimate_tokens():
    text = "Hello world! This is a test string."
    tokens = estimate_tokens(text)
    assert tokens > 0


def test_memory_compaction():
    # Set a small context limit to trigger compaction quickly
    mem = MemoryManager(context_limit=100, target_ratio=0.5)

    mem.add_message("system", "You are CampusCLI.")
    for i in range(10):
        mem.add_message("user", f"Here is query number {i} with some long text to fill up the context window.")
        mem.add_message("assistant", f"Here is response number {i} explaining the solution.")

    # Should have triggered compaction
    msgs = mem.get_messages()
    assert len(msgs) < 21
    # Check that system summary or system message exists
    assert any("compacted" in str(m.get("content", "")) for m in msgs)
