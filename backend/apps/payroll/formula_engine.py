import ast
import operator
from decimal import Decimal, InvalidOperation

class FormulaError(Exception):
    """Base exception for formula parsing and evaluation errors."""
    pass

class SafeFormulaEvaluator:
    """
    Safely evaluates payroll formulas using Python's AST.
    Strictly whitelists permitted AST nodes (math operations, literals, valid variables).
    """

    ALLOWED_OPERATORS = {
        ast.Add: operator.add,
        ast.Sub: operator.sub,
        ast.Mult: operator.mul,
        ast.Div: operator.truediv,
        ast.UAdd: operator.pos,
        ast.USub: operator.neg,
    }

    def __init__(self, allowed_variables: set):
        self.allowed_variables = allowed_variables

    def evaluate(self, expression: str, context: dict) -> Decimal:
        """
        Evaluate a formula string safely against a context dictionary.
        Returns the computed value as a Decimal.
        """
        if not expression or not expression.strip():
            return Decimal('0.00')

        try:
            tree = ast.parse(expression.strip(), mode='eval')
        except SyntaxError as e:
            raise FormulaError(f"Invalid formula syntax: {str(e)}")

        # Evaluate the AST recursively
        result = self._eval_node(tree.body, context)
        return Decimal(str(result))

    def _eval_node(self, node, context):
        if isinstance(node, ast.Constant):
            if not isinstance(node.value, (int, float, Decimal)):
                raise FormulaError(f"Unsupported literal type: {type(node.value)}")
            return Decimal(str(node.value))

        elif hasattr(ast, 'Num') and isinstance(node, getattr(ast, 'Num')):
            return Decimal(str(node.n))

        elif isinstance(node, ast.Name):
            if not isinstance(node.ctx, ast.Load):
                raise FormulaError("Assignment or deletion in formula is not allowed.")
            var_name = node.id
            if var_name not in self.allowed_variables:
                raise FormulaError(f"Unknown or unapproved variable: {var_name}")
            if var_name not in context:
                raise FormulaError(f"Variable '{var_name}' not provided in context.")
            
            val = context[var_name]
            try:
                return Decimal(str(val))
            except (ValueError, TypeError, InvalidOperation):
                raise FormulaError(f"Variable '{var_name}' must be a number, got {type(val)}")

        elif isinstance(node, ast.BinOp):
            left = self._eval_node(node.left, context)
            right = self._eval_node(node.right, context)
            op = type(node.op)
            
            if op not in self.ALLOWED_OPERATORS:
                raise FormulaError(f"Unsupported binary operator: {op.__name__}")
                
            if op == ast.Div and right == 0:
                raise FormulaError("Division by zero in formula.")
                
            return self.ALLOWED_OPERATORS[op](left, right)

        elif isinstance(node, ast.UnaryOp):
            operand = self._eval_node(node.operand, context)
            op = type(node.op)
            if op not in self.ALLOWED_OPERATORS:
                raise FormulaError(f"Unsupported unary operator: {op.__name__}")
            return self.ALLOWED_OPERATORS[op](operand)

        else:
            raise FormulaError(f"Unsupported expression node: {type(node).__name__}")
