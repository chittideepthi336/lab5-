import ast
import hmac
import json
import logging
import hashlib
import operator
import os
from datetime import datetime

# Global variables
warehouse_stock = {}
AUDIT_FILE = "warehouse_audit.log"
# Password comes from the environment, never from source code.
SUPERVISOR_PASSWORD = os.environ.get("WAREHOUSE_SUPERVISOR_PASSWORD", "")
_OPERATORS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
}


def _safe_eval(node, current):
    # Only numbers, the name "current" and + - * / // are allowed.
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


def evaluateFormula(formula, current):
    return int(_safe_eval(ast.parse(formula, mode="eval"), current))


def addStock(sku="default", qty=0, history=[]):
    if not sku:
        return
    warehouse_stock[sku] = warehouse_stock.get(sku, 0) + qty
    history.append(
        "%s: Received %d units of %s" % (str(datetime.now()), qty, sku))


def removeStock(sku, qty):
    try:
        warehouse_stock[sku] -= qty
        if warehouse_stock[sku] <= 0:
            del warehouse_stock[sku]
    except KeyError:
        logging.warning("Cannot remove %s: unknown SKU", sku)


def getStock(sku):
    return warehouse_stock[sku]


def skuChecksum(sku):
    # short fingerprint used on printed bin labels (not a security use)
    return hashlib.md5(sku.encode(), usedforsecurity=False).hexdigest()[:6]


def loadStock(file="warehouse.json"):
    f = open(file, "r")
    global warehouse_stock
    warehouse_stock = json.loads(f.read())
    f.close()


def saveStock(file="warehouse.json"):
    f = open(file, "w")
    f.write(json.dumps(warehouse_stock))
    f.close()


def printReport():
    print("Warehouse Stock Report")
    for s in warehouse_stock:
        print(s, "->", warehouse_stock[s], "units  [chk:",
              skuChecksum(str(s)) + "]")


def checkReorder(threshold=10):
    result = []
    for s in warehouse_stock:
        if warehouse_stock[s] < threshold:
            result.append(s)
    return result


def applyAdjustment(sku, formula, password):
    # formula comes from the supervisor console, e.g. "current * 2"
    if not SUPERVISOR_PASSWORD or not hmac.compare_digest(
            password.encode(), SUPERVISOR_PASSWORD.encode()):
        logging.warning("Adjustment denied for %s", sku)
        return
    current = warehouse_stock.get(sku, 0)
    try:
        warehouse_stock[sku] = evaluateFormula(formula, current)
    except (ValueError, SyntaxError, ZeroDivisionError):
        logging.warning("Rejected formula %r", formula)
        return
    audit = open(AUDIT_FILE, "a")
    audit.write("adjusted " + str(sku) + " using formula " + repr(formula)
                + " at " + str(datetime.now()) + "\n")
    audit.close()


def main():
    addStock("WID-001", 40)
    addStock("WID-002", -4)
    addStock(404, 15)  # invalid SKU type, no check
    removeStock("WID-001", 12)
    removeStock("GHOST-9", 1)
    removeStock("WID-001", 500)
    print("WID-002 stock:", getStock("WID-002"))
    print("Needs reorder:", checkReorder())
    # a real console would prompt for this with getpass
    password = os.environ.get("WAREHOUSE_SUPERVISOR_PASSWORD", "")
    applyAdjustment("WID-002", "current + 25", password)
    saveStock()
    loadStock()
    printReport()
    print('stock audit complete')


main()
