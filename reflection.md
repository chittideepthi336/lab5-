# Reflection

*(The lab handout PDF does not print the four reflection questions, so these are the standard ones for this lab. Check the wording against your course page and adjust headings if they differ.)*

## 1. Which issues were the easiest and which the hardest to fix?

Easiest were the mechanical ones: Flake8 blank lines, line length and trailing whitespace, unused imports and the unused `total_units` variable, and the Pylint naming and docstring warnings. They need no design decision.

Hardest was `eval()`. Deleting it would have broken the supervisor feature, so I had to replace it with a small `ast`-based evaluator that only allows numbers, `current` and basic arithmetic. The second hardest was the logic bugs the tools never flagged: overselling deleted the whole SKU, and negative quantities were accepted. Those required reading the program output and deciding what correct behaviour should be.

## 2. Did the tools report any false positives, or miss real problems?

False positive: in my first fixed version Bandit B105 flagged my constant for the *name* of the environment variable (`PASSWORD_ENV_VAR = "WAREHOUSE_SUPERVISOR_PASSWORD"`) as a hardcoded password, only because the variable name contained "PASSWORD". I renamed it to `SUPERVISOR_ENV_KEY`. Bandit B324 on MD5 is also arguable here: the hash is just a label fingerprint, so I kept MD5 and marked it `usedforsecurity=False` rather than changing every printed label.

Missed: none of the three tools caught that `removeStock("WID-001", 500)` deletes the SKU, that `addStock("WID-002", -4)` stores negative stock, that an integer SKU becomes a string after the JSON round trip, or that the audit log is open to log injection. I only found the first three by running the program and reading its output (stock `-4`, WID-001 missing from the report).

## 3. How would you integrate static analysis into a real development workflow?

Run Flake8 and Pylint as a pre-commit hook so style and quality problems never reach the repository, and run all three tools (Pylint, Flake8, Bandit) in CI on every pull request, failing the build on any Bandit finding and on a Pylint score below an agreed threshold (for example 9.5). Pin tool versions so results are repeatable, and allow suppressions (`# nosec`, `# pylint: disable`) only with a written justification in review.

## 4. What improvements in code quality, security and readability did you notice?

Quality: Pylint went from 4.48/10 to 10.00/10, Flake8 from 19 issues to 0. Security: Bandit went from 5 findings (1 High, 2 Medium, 2 Low) to none; arbitrary code execution through `eval` is gone, the password is no longer in source, and it is compared in constant time. Readability and maintainability: snake_case names, docstrings, `with` blocks, no global rebinding, no shared mutable default, and clear errors instead of silent `pass`. Behaviour also improved: stock can no longer go negative or vanish, and every rejected operation is logged. The main lesson is that static analysis is a safety net, not a substitute for running the program and reading its output.
