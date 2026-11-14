"""Local IFC extraction and deterministic execution of the shared contracts."""

__version__ = "0.3.0"

from .engine import IfcQueryEngine, QueryError

__all__ = ["IfcQueryEngine", "QueryError", "__version__"]
