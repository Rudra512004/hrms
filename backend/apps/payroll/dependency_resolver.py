import ast
from collections import defaultdict, deque

class DependencyError(Exception):
    pass

class ComponentDependencyResolver:
    """
    Extracts dependencies from component formulas and topologically sorts components
    to determine the correct evaluation order.
    """

    def __init__(self, provided_variables: set):
        self.provided_variables = provided_variables

    def extract_variables(self, expression: str) -> set:
        """
        Parses a formula string and extracts all variable names.
        """
        if not expression or not expression.strip():
            return set()
        
        try:
            tree = ast.parse(expression.strip(), mode='eval')
        except SyntaxError as e:
            raise DependencyError(f"Syntax error in formula: {str(e)}")

        variables = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Name):
                variables.add(node.id)
                
        return variables

    def resolve_order(self, components: list) -> list:
        """
        Takes a list of component definitions.
        Each component must have:
        - `code`: str (unique identifier)
        - `formula_expression`: str (the formula to evaluate, or empty)
        - `calculation_type`: str ('formula', 'percentage', 'flat')

        Returns a list of `code`s in topological order.
        """
        graph = defaultdict(list)
        in_degree = defaultdict(int)
        
        # Track defined codes to ensure we don't reference missing components
        component_codes = {comp['code'] for comp in components}

        for comp in components:
            code = comp['code']
            in_degree[code] = 0  # Initialize in_degree

        for comp in components:
            code = comp['code']
            
            # If it's a flat component, it has no dependencies (unless it's an override that looks like a formula? No)
            expr = comp.get('formula_expression', '')
            if comp.get('calculation_type') == 'flat' or not expr:
                continue

            dependencies = self.extract_variables(expr)

            for dep in dependencies:
                # Is this dependency a provided global variable (like BASIC)?
                if dep in self.provided_variables:
                    continue
                
                # If not a global variable, it must be another component
                if dep not in component_codes:
                    raise DependencyError(f"Component '{code}' references unknown variable/component '{dep}'")
                
                if dep == code:
                    raise DependencyError(f"Component '{code}' contains self-reference.")

                # Edge goes from dependency -> dependent
                graph[dep].append(code)
                in_degree[code] += 1

        # Kahn's algorithm for topological sorting
        queue = deque([node for node in component_codes if in_degree[node] == 0])
        sorted_order = []

        # To ensure deterministic ordering among independent components, we sort the queue output
        # However, a standard queue isn't always deterministic if we don't sort the initial independent nodes
        # Let's use a sorted queue approach manually for true determinism.
        
        # We'll just collect zero-degree nodes, sort them, and process.
        sorted_nodes_to_process = sorted([node for node in component_codes if in_degree[node] == 0])
        
        while sorted_nodes_to_process:
            # Pop the first element deterministically
            current = sorted_nodes_to_process.pop(0)
            sorted_order.append(current)

            for neighbor in sorted(graph[current]):
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    sorted_nodes_to_process.append(neighbor)
            
            # Keep it sorted to guarantee deterministic processing
            sorted_nodes_to_process.sort()

        if len(sorted_order) != len(component_codes):
            # Find which components are stuck in a cycle
            stuck = [node for node in component_codes if in_degree[node] > 0]
            raise DependencyError(f"Circular dependency detected involving components: {', '.join(sorted(stuck))}")

        return sorted_order
