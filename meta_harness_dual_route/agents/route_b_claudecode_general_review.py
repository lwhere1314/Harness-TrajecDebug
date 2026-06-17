"""Backward-compatible import path for the Claude Code adaptation attempt.

This path is retained so archived raw logs and old invocations remain
importable. New runs should use
`claude_code_generic_review_adaptation:AgentHarness`, which makes clear that
this is not the upstream Meta-Harness protocol.
"""

from meta_harness_dual_route.agents.claude_code_generic_review_adaptation import AgentHarness
