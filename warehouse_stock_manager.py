"""Warehouse stock manager: receive, issue, report and adjust stock."""
import ast
import hashlib
import hmac
import json
import logging
import operator
import os
from datetime import datetime

AUDIT_FILE = "warehouse_audit.log"
STOCK_FILE = "warehouse.json"
SUPERVISOR_ENV_KEY = "WAREHOUSE_SUPERVISOR_PASSWORD"
WAREHOUSE_STOCK = {}

_OPERATORS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
}


def _safe_eval(node, current):
    """Evaluate a parsed formula: numbers, 'current' and + - * / // only."""
    if isinstance(node, ast.Expression):
        return _safe_eval(node.body, current)
    if isinstance(node, ast.Constant) and type(node.value) in (int, float):
        return node.value
    if isinstance(node, ast.Name) and node.id == "current":
        return current
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
        return -_safe_eval(node.operand, current)
    if isinstance(node, ast.BinOp) and type(node.op) in _OPERATORS:
        left = _safe_eval(node.left, current)
        right = _safe_eval(node.right, current)
        return _OPERATORS[type(node.op)](left, right)
    raise ValueError("unsupported formula")


def evaluate_formula(formula, current):
    """Return the integer result of a formula such as 'current * 2'."""
    return int(_safe_eval(ast.parse(formula, mode="eval"), current))


def _check_sku(sku):
    """Raise ValueError unless ``sku`` is a non-empty string."""
    if not isinstance(sku, str) or not sku.strip():
        raise ValueError(f"Invalid SKU: {sku!r}")


def _check_qty(sku, qty):
    """Raise ValueError unless ``qty`` is a positive integer."""
    if not isinstance(qty, int) or isinstance(qty, bool) or qty <= 0:
        raise ValueError(f"Invalid quantity for {sku}: {qty!r}")


def add_stock(sku, qty, history=None):
    """Receive ``qty`` units of ``sku`` and return the history log."""
    if history is None:
        history = []
    _check_sku(sku)
    _check_qty(sku, qty)
    WAREHOUSE_STOCK[sku] = WAREHOUSE_STOCK.get(sku, 0) + qty
    history.append(f"{datetime.now()}: Received {qty} units of {sku}")
    return history


def remove_stock(sku, qty):
    """Issue ``qty`` units of ``sku``; refuse unknown SKUs and overselling."""
    if sku not in WAREHOUSE_STOCK:
        raise ValueError(f"Unknown SKU: {sku!r}")
    _check_qty(sku, qty)
    if qty > WAREHOUSE_STOCK[sku]:
        raise ValueError(
            f"Cannot issue {qty} of {sku}: only {WAREHOUSE_STOCK[sku]} left")
    WAREHOUSE_STOCK[sku] -= qty


def get_stock(sku):
    """Return units on hand for ``sku`` (0 if the SKU is unknown)."""
    return WAREHOUSE_STOCK.get(sku, 0)


def sku_checksum(sku):
    """Return the short fingerprint printed on bin labels (not security)."""
    digest = hashlib.md5(sku.encode("utf-8"), usedforsecurity=False)
    return digest.hexdigest()[:6]


def load_stock(file=STOCK_FILE):
    """Replace the in-memory stock with the contents of a JSON file."""
    with open(file, "r", encoding="utf-8") as handle:
        data = json.load(handle)
    WAREHOUSE_STOCK.clear()
    WAREHOUSE_STOCK.update(data)


def save_stock(file=STOCK_FILE):
    """Write the current stock levels to a JSON file."""
    with open(file, "w", encoding="utf-8") as handle:
        json.dump(WAREHOUSE_STOCK, handle)


def print_report():
    """Print every SKU with its quantity and label checksum."""
    print("Warehouse Stock Report")
    for sku, qty in WAREHOUSE_STOCK.items():
        print(f"{sku} -> {qty} units  [chk: {sku_checksum(str(sku))}]")


def check_reorder(threshold=10):
    """Return the SKUs whose quantity is below ``threshold``."""
    return [sku for sku, qty in WAREHOUSE_STOCK.items() if qty < threshold]


def apply_adjustment(sku, formula, password):
    """Set a SKU's quantity from a formula; return True if it was applied."""
    expected = os.environ.get(SUPERVISOR_ENV_KEY, "")
    if not expected or not hmac.compare_digest(
            password.encode("utf-8"), expected.encode("utf-8")):
        logging.warning("Adjustment denied for %s", sku)
        return False
    try:
        new_qty = evaluate_formula(formula, WAREHOUSE_STOCK.get(sku, 0))
        if new_qty < 0:
            raise ValueError("result would be negative")
    except (ValueError, SyntaxError, ZeroDivisionError) as err:
        logging.warning("Rejected formula %r: %s", formula, err)
        return False
    WAREHOUSE_STOCK[sku] = new_qty
    with open(AUDIT_FILE, "a", encoding="utf-8") as audit:
        audit.write(
            f"adjusted {sku} using formula {formula!r} at {datetime.now()}\n")
    return True


def _attempt(action, *args):
    """Run one demo step, logging (not hiding) any rejected input."""
    try:
        action(*args)
    except ValueError as err:
        logging.warning("Rejected: %s", err)


def main():
    """Run the built-in demo."""
    logging.basicConfig(level=logging.INFO,
                        format="%(levelname)s: %(message)s")
    _attempt(add_stock, "WID-001", 40)
    _attempt(add_stock, "WID-002", -4)
    _attempt(add_stock, 404, 15)
    _attempt(remove_stock, "WID-001", 12)
    _attempt(remove_stock, "GHOST-9", 1)
    _attempt(remove_stock, "WID-001", 500)
    print("WID-002 stock:", get_stock("WID-002"))
    print("Needs reorder:", check_reorder())
    # a real supervisor console would prompt for this with getpass
    password = os.environ.get(SUPERVISOR_ENV_KEY, "")
    apply_adjustment("WID-002", "current + 25", password)
    save_stock()
    load_stock()
    print_report()
    print("stock audit complete")


if __name__ == "__main__":
    main()
