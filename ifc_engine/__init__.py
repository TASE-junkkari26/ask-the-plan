"""Local IFC extraction and deterministic execution of the shared contracts."""

__version__ = "0.4.0"

from .engine import IfcQueryEngine, QueryError

__all__ = ["IfcQueryEngine", "QueryError", "__version__"]
