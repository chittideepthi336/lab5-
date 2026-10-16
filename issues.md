# Issues found in `warehouse_stock_manager.py`

Line numbers refer to the **original** file. Sorted by severity (high and medium first).
Baseline before fixing: Pylint 4.48/10, Bandit 5 issues (1 High, 2 Medium, 2 Low), Flake8 19 issues.

| Issue | Type | Line(s) | Description | Fix Approach |
|-------|------|---------|-------------|--------------|
| Weak MD5 hash | Security (High) | 26 | Bandit B324 (CWE-327): `hashlib.md5(...)` used for the bin-label fingerprint. MD5 is broken for security use. | The label is only a short fingerprint, not a security control, so kept MD5 (keeps printed labels valid) and declared it with `usedforsecurity=False`. Added a comment explaining why. |
| `eval()` on supervisor formula | Security (Medium) | 52 | Bandit B307 / Pylint W0123: `eval(formula, {"current": current})` executes arbitrary Python. `eval` still injects builtins into the globals dict, so a formula like `__import__('os').system(...)` runs OS commands. | Replaced with an `ast`-based evaluator that accepts only numbers, the name `current` and `+ - * / //`. Anything else raises `ValueError` and is logged and rejected. |
| `eval()` in demo code | Security (Medium) | 69 | Bandit B307 / Pylint W0123: `eval("print('stock audit complete')")` has no reason to exist. | Replaced with a plain `print(...)`. |
| Overselling silently deletes the SKU | Bug (logic, not tool-flagged) | 15-21 | `removeStock("WID-001", 500)` on 28 units makes stock -472, which is `<= 0`, so the whole SKU is deleted. WID-001 vanishes from the report and stock data is lost. | `remove_stock` now refuses to issue more than is on hand (raises `ValueError`), leaves stock unchanged, and keeps zero-stock SKUs so `check_reorder` can flag them. |
| Invalid input accepted | Bug (logic, not tool-flagged) | 10-14, 22-23 | `addStock("WID-002", -4)` stores -4 stock (demo prints `WID-002 stock: -4`). `addStock(404, 15)` accepts an integer SKU (which JSON also turns into the string `"404"` on reload). `if not sku: return` silently drops bad input. `getStock` raises `KeyError` on unknown SKUs. | Added `_check_sku` (non-empty string) and `_check_qty` (positive int) validation that raises `ValueError`; demo logs rejections. `get_stock` returns 0 for unknown SKUs. |
| Hardcoded password | Security (Low) | 9, 49 | Bandit B105 (CWE-259): `SUPERVISOR_PASSWORD = "wh-admin-1234"` in source. The same password is also repeated in the demo call (line 65). Also compared with `!=` (not constant-time). | Password now read from the `WAREHOUSE_SUPERVISOR_PASSWORD` environment variable; compared with `hmac.compare_digest`; adjustments are denied if it is unset. |
| Bare `except` + `pass` | Security/Quality (Low) | 20-21 | Bandit B110, Flake8 E722, Pylint W0702: swallows every error, so removing the unknown SKU `GHOST-9` fails silently. | Removed the try/except; unknown SKU now raises a clear `ValueError` which the caller logs. (Intermediate commit used `except KeyError` + `logging.warning`.) |
| Mutable default argument | Bug | 10 | Pylint W0102: `history=[]` is created once and shared across every call. | Default `history=None`, create a new list inside the function, and return it. |
| Files opened without `with`, no encoding; `global` | Quality | 27-35, 53-55 | Pylint R1732, W1514, W0603: files are not closed if an exception occurs, encoding is platform-dependent, and `global warehouse_stock` rebinds module state. | Use `with open(..., encoding="utf-8")`, `json.load`/`json.dump`, and `clear()` + `update()` instead of `global`. |
| Unused imports / variable | Quality | 2, 4, 45 | Flake8 F401 (`logging`, `os`), F841 and Pylint W0611/W0612 (`total_units`). Dead code. | Removed `total_units`; `logging` and `os` are now genuinely used. |
| Non-PEP8 names, missing docstrings | Quality | 1, 10-56 | Pylint C0103 (camelCase function names), C0114/C0116 (no module/function docstrings). | Renamed to snake_case (`add_stock`, `remove_stock`, ...), added docstrings, added `if __name__ == "__main__":` guard. |
| Style violations | Style | 10-70 | Flake8 E302/E305 (missing blank lines), E501 (lines 14, 39, 54 over 79 chars), W291 trailing whitespace (line 45), Pylint C0301/C0303. | Reformatted to PEP 8: two blank lines between definitions, wrapped long lines, stripped whitespace. |
| Log injection in audit file | Security (Low, not tool-flagged) | 54 | The raw formula string is concatenated into the audit log, so a newline in the formula can forge log entries. | Log `{formula!r}` so control characters are escaped; use an f-string inside `with`. |

## Results after fixing

| Tool | Before | After |
|------|--------|-------|
| Pylint | 4.48/10 | 10.00/10 |
| Bandit | 5 issues (1 High, 2 Medium, 2 Low) | No issues identified |
| Flake8 | 19 issues | 0 issues |

Demo output before vs after: `WID-002 stock: -4` and WID-001 missing from the report became `WID-002 stock: 0`, with both WID-001 (28) and WID-002 (25) in the final report and every bad call logged as a warning.
