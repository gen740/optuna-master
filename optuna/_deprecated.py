import functools
import inspect
import textwrap
from typing import Any
from typing import Callable
from typing import Optional
from typing import overload
from typing import Type
from typing import TypeVar
from typing import Union
import warnings

from packaging import version
from typing_extensions import ParamSpec

from optuna._experimental import _get_docstring_indent
from optuna._experimental import _validate_version

FT = TypeVar("FT")
FP = ParamSpec("FP")
CT = TypeVar("CT")

_DEPRECATION_NOTE_TEMPLATE = """

.. warning::
    Deprecated in v{d_ver}. This feature will be removed in the future. The removal of this
    feature is currently scheduled for v{r_ver}, but this schedule is subject to change.
    See https://github.com/optuna/optuna/releases/tag/v{d_ver}.
"""


_DEPRECATION_WARNING_TEMPLATE = (
    "{name} has been deprecated in v{d_ver}. "
    "This feature will be removed in v{r_ver}. "
    "See https://github.com/optuna/optuna/releases/tag/v{d_ver}."
)


def _validate_two_version(old_version: str, new_version: str) -> None:
    if version.parse(old_version) > version.parse(new_version):
        raise ValueError(
            "Invalid version relationship. The deprecated version must be smaller than "
            "the removed version, but (deprecated version, removed version) = ({}, {}) are "
            "specified.".format(old_version, new_version)
        )


def _format_text(text: str) -> str:
    return "\n\n" + textwrap.indent(text.strip(), "    ") + "\n"


def deprecated(
    deprecated_version: str,
    removed_version: str,
    name: Optional[str] = None,
    text: Optional[str] = None,
) -> Union[Callable[[CT], CT], Callable[FP, FT]]:
    """Decorate class or function as deprecated.

    Args:
        deprecated_version:
            The version in which the target feature is deprecated.
        removed_version:
            The version in which the target feature will be removed.
        name:
            The name of the feature. Defaults to the function or class name. Optional.
        text:
            The additional text for the deprecation note. The default note is build using specified
            ``deprecated_version`` and ``removed_version``. If you want to provide additional
            information, please specify this argument yourself.

            .. note::
                The default deprecation note is as follows: "Deprecated in v{d_ver}. This feature
                will be removed in the future. The removal of this feature is currently scheduled
                for v{r_ver}, but this schedule is subject to change. See
                https://github.com/optuna/optuna/releases/tag/v{d_ver}."

            .. note::
                The specified text is concatenated after the default deprecation note.
    """

    _validate_version(deprecated_version)
    _validate_version(removed_version)
    _validate_two_version(deprecated_version, removed_version)

    @overload
    def _deprecated_wrapper(f: Callable[FP, FT]) -> Callable[FP, FT]:
        ...

    @overload
    def _deprecated_wrapper(f: CT) -> CT:
        ...

    def _deprecated_wrapper(f: Any) -> Any:
        # f is either func or class.

        def _deprecated_func(func: Callable[FP, FT]) -> Callable[FP, FT]:
            """Decorates a function as deprecated.

            This decorator is supposed to be applied to the deprecated function.
            """
            if func.__doc__ is None:
                func.__doc__ = ""

            note = _DEPRECATION_NOTE_TEMPLATE.format(
                d_ver=deprecated_version, r_ver=removed_version
            )
            if text is not None:
                note += _format_text(text)
            indent = _get_docstring_indent(func.__doc__)
            func.__doc__ = func.__doc__.strip() + textwrap.indent(note, indent) + indent

            # TODO(mamu): Annotate this correctly.
            @functools.wraps(func)
            def new_func(*args: Any, **kwargs: Any) -> Any:
                message = _DEPRECATION_WARNING_TEMPLATE.format(
                    name=(name if name is not None else func.__name__),
                    d_ver=deprecated_version,
                    r_ver=removed_version,
                )
                if text is not None:
                    message += " " + text
                warnings.warn(message, FutureWarning, stacklevel=2)

                return func(*args, **kwargs)

            return new_func

        def _deprecated_class(cls: Type[CT]) -> Type[CT]:
            """Decorates a class as deprecated.

            This decorator is supposed to be applied to the deprecated class.
            """
            _original_init = cls.__init__

            @functools.wraps(_original_init)
            def wrapped_init(self, *args, **kwargs) -> None:  # type: ignore
                message = _DEPRECATION_WARNING_TEMPLATE.format(
                    name=(name if name is not None else cls.__name__),
                    d_ver=deprecated_version,
                    r_ver=removed_version,
                )
                if text is not None:
                    message += " " + text
                warnings.warn(
                    message,
                    FutureWarning,
                    stacklevel=2,
                )

                _original_init(self, *args, **kwargs)

            setattr(cls, "__init__", wrapped_init)

            if cls.__doc__ is None:
                cls.__doc__ = ""

            note = _DEPRECATION_NOTE_TEMPLATE.format(
                d_ver=deprecated_version, r_ver=removed_version
            )
            if text is not None:
                note += _format_text(text)
            indent = _get_docstring_indent(cls.__doc__)
            cls.__doc__ = cls.__doc__.strip() + textwrap.indent(note, indent) + indent

            return cls

        return _deprecated_class(f) if inspect.isclass(f) else _deprecated_func(f)

    return _deprecated_wrapper
