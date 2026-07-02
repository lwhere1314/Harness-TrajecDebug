from harbor.agents.terminus_2.terminus_2 import Terminus2


class AgentHarness(Terminus2):
    """General Terminus2 candidate with a final reliability review."""

    _GENERAL_REVIEW = """

General harness review:
- Before declaring completion, check whether the requested behavior has edge
  states involving interruption, cleanup, background work, concurrency, partial
  files, subprocesses, timeouts, retries, or external services.
- Prefer a small self-check that exercises the public task contract when it is
  cheap to do so.
- Keep the final state minimal and reproducible; avoid leaving avoidable
  background processes, temporary artifacts, or half-applied setup behind.
"""

    async def run(self, instruction, environment, context) -> None:
        return await super().run(instruction + self._GENERAL_REVIEW, environment, context)

    def _get_completion_confirmation_message(self, terminal_output: str) -> str:
        base = super()._get_completion_confirmation_message(terminal_output)
        return (
            base
            + "\n\nBefore confirming, perform a general reliability review for "
            "edge states, cleanup, background work, interruption handling, and "
            "whether a cheap public-contract self-check is available."
        )
