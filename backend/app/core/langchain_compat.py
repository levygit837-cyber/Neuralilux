import inspect
from typing import ForwardRef


def patch_forward_ref_evaluate_for_python312() -> None:
    """
    Python 3.12 changed ForwardRef._evaluate to require recursive_guard
    as a keyword-only argument. Older LangChain/LangSmith dependency
    combinations still call it positionally during import.
    """
    original = getattr(ForwardRef, "_evaluate", None)
    if original is None or getattr(original, "_neuralilux_patched", False):
        return

    recursive_guard = inspect.signature(original).parameters.get("recursive_guard")
    if recursive_guard is None or recursive_guard.kind is not inspect.Parameter.KEYWORD_ONLY:
        return

    def _patched(self, globalns, localns, type_params=None, *, recursive_guard=None):
        if recursive_guard is None:
            if isinstance(type_params, set):
                recursive_guard = type_params
            else:
                recursive_guard = set()
        return original(self, globalns, localns, recursive_guard=recursive_guard)

    _patched._neuralilux_patched = True  # type: ignore[attr-defined]
    ForwardRef._evaluate = _patched


patch_forward_ref_evaluate_for_python312()
