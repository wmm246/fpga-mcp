## Summary

<!-- One or two sentences: what does this PR change? -->

## Motivation

<!-- Why is this needed? Link issues with "Fixes #123" / "Closes #123". -->

## What changed

<!-- Bullet list of the main changes. -->

- 
- 
- 

## Checklist

- [ ] `pytest` passes locally (`pip install -e '.[dev]' && pytest`)
- [ ] `ruff check src tests` is clean
- [ ] If new tool(s) added: spec lives in `src/fpga_mcp/tool_defs/<vendor>.py`
      and follows the naming convention (`viv_` / `q_` / `a_` prefix, or no
      prefix for common)
- [ ] If new tool(s) added: `tests/test_tool_defs.py` catalogue invariants
      still pass (no duplicate names, every spec has summary + category)
- [ ] README / CHANGELOG updated if user-visible
- [ ] No new dependencies unless discussed in the PR description

## Test plan

<!-- How did you verify this works? -->

```bash
# Commands you ran.
pytest -k <pattern>
ruff check src tests
```

## Screenshots / logs

<!-- Optional. For UI or large output changes. -->
