# SPDX-FileCopyrightText: 2026 Ian Pilcher <arequipeno@gmail.com>
# SPDX-License-Identifier: GPL-3.0-or-later


import argparse
import collections.abc
import dataclasses
import enum
import re
import types
import typing


class _NoValueType(enum.Enum):
    """Unique sentinel type."""

    _NO_VALUE = "_NO_VALUE"
    """Unique sentinel value."""

    def __bool__(self) -> bool:
        '''Make the sentinel "falsy."'''
        return False

_NO_VALUE: typing.Final = _NoValueType._NO_VALUE
"""Unique sentinel value."""


class _AddArgumentKwargs[T](typing.TypedDict, total=False):
    """Keyword arguments passed to :module:`argparse`
    :meth:`~argparse._ActionsContainer.add_argument` method.
    """
    type: argparse._ActionType
    default: T
    required: bool
    choices: collections.abc.Iterable[T]
    action: str | type[argparse.Action]
    nargs: str  # Only used for optional positional arguments
    help: str
    metavar: str
    deprecated: bool
    dest: str


class _ConfigItem:
    pass


@dataclasses.dataclass
class _Group(_ConfigItem):
    title: str | None=None
    description: str | None=None
    arg_group: argparse._ArgumentGroup = dataclasses.field(init=False)


def group(title: str | None=None, description: str | None=None) -> _Group:
    return _Group(title, description)


@dataclasses.dataclass(kw_only=True)
class _MXGroup(_ConfigItem):
    required: bool=False
    group: str | None=None
    mx_group: argparse._MutuallyExclusiveGroup = dataclasses.field(init=False)


def mxgroup(*, required: bool=False, group: str | None=None) -> _MXGroup:
    return _MXGroup(required=required, group=group)


@dataclasses.dataclass
class _Argument[T](_ConfigItem):

    default: T | _NoValueType
    type: collections.abc.Callable[[str], T] | str | None
    positional: bool | None
    required: bool | None
    sentinel: object
    choices: collections.abc.Iterable[T] | None
    group: str | None
    short: str | None
    help: str | None
    metavar: str | None
    deprecated: bool

    # These are set during post-processing by Args.__init_subclass__
    _name: str = dataclasses.field(init=False)
    # TODO: type_hint will be typing.TypeForm[T] in Python 3.15+
    _type_hint: object = dataclasses.field(init=False)
    _factory: collections.abc.Callable[[str], T] | str=(
        dataclasses.field(init=False)
    )



def arg[T](
        *,
        default: T | _NoValueType=_NO_VALUE,
        type: collections.abc.Callable[[str], T] | str | None=None,
        positional: bool | None=None,
        required: bool | None=None,
        sentinel: object=_NO_VALUE,
        choices: collections.abc.Iterable[T] | None=None,
        group: str | None=None,
        short: str | None=None,
        help: str | None=None,
        metavar: str | None=None,
        deprecated: bool=False
) -> T:
    a = _Argument(
        default, type, positional, required, sentinel, choices, group, short,
        help, metavar, deprecated
    )
    return typing.cast(T, a)


# ------------------------------------------------------------------------------
# Args helper functions
# ------------------------------------------------------------------------------


_DEFAULT_SENTINEL_TYPES: typing.Final = {types.NoneType, types.EllipsisType}


def _resolve_type[T](hint: object, sentinel: object=_NO_VALUE) -> type[T]:
    if sentinel is _NO_VALUE:
        sentinel_types = _DEFAULT_SENTINEL_TYPES
    else:
        sentinel_types = {type(sentinel)}
    if hint in sentinel_types:
        raise ValueError(f"Hint is a standalone sentinel type: {hint}")
    origin = typing.get_origin(hint)
    if origin is types.UnionType:
        hints = [h for h in typing.get_args(hint) if h not in sentinel_types]
        if len(hints) == 0:
            raise ValueError(f"Hint contains no non-sentinel types: {hint}")
        if len(hints) > 1:
            raise ValueError(f"Hint contains multiple concrete types: {hint}")
        hint = hints[0]
        origin = typing.get_origin(hint)
    if origin is not None:
        raise ValueError(f"Hint is a non-union parameterized type: {hint}")
    if not isinstance(hint, type):
        raise ValueError(f"Hint does not identify a concrete class: {hint}")
    return hint


def _fix_name(name: str) -> str:
    """Replaces non-leading underscores in :arg:`name` with hypens."""
    base = name.lstrip("_")
    prefix = "_" * (len(name) - len(base))
    return prefix + base.replace("_", "-")


def _add_arg_kwargs[T](argument: _Argument[T]) -> _AddArgumentKwargs[T]:
    kwargs: _AddArgumentKwargs[T] = {"deprecated": argument.deprecated}
    if argument.default is not _NO_VALUE:
        kwargs["default"] = argument.default
    if argument.choices is not None:
        kwargs["choices"] = argument.choices
    if argument.help is not None:
        kwargs["help"] = argument.help
    if argument.metavar is not None:
        kwargs["metavar"] = argument.metavar
    return kwargs


def _add_flag[T](
        ac: argparse._ActionsContainer, dest: str, argument: _Argument[T]
) -> None:
    argument._name = "--" + _fix_name(dest)
    name_or_flags = [argument._name]
    if argument.short is not None:
        if not (
            len(argument.short) == 2
            and argument.short[0] == "-"
            and argument.short[1].isalnum()
        ):
            raise ValueError(f"Invalid short option name: {argument.short}")
        name_or_flags.append(argument.short)
    kwargs = _add_arg_kwargs(argument)
    kwargs["dest"] = dest
    if argument._factory is bool:
        kwargs["action"] = "store_true"
    else:
        kwargs["type"] = argument._factory
    if argument.required is not None:
        kwargs["required"] = argument.required
    ac.add_argument(*name_or_flags, **kwargs)


def _add_positional[T](
        ac: argparse._ActionsContainer, dest: str, argument: _Argument[T]
) -> None:
    argument._name = _fix_name(dest)
    if argument.short is not None:
        raise ValueError(
            f"Short option ({argument.short}) specified "
            f"for positional argument: {dest}"
        )
    kwargs = _add_arg_kwargs(argument)
    kwargs["type"] = argument._factory
    if argument.required is False:
        kwargs["nargs"] = "?"
    ac.add_argument(dest, **kwargs)


class Arguments:

    __parser: typing.ClassVar[argparse.ArgumentParser]
    __arguments: typing.ClassVar[dict[str, _Argument[object]]]
    __arg_groups: typing.ClassVar[dict[str, _Group]]
    __mx_groups: typing.ClassVar[dict[str, _MXGroup]]
    __ap_groups: typing.ClassVar[dict[str, argparse._ArgumentGroup]]

    def __new__(cls) -> typing.Self:
        """Prevent abstract class instantiation."""
        if cls is Arguments:
            raise TypeError(
                f"Cannot instantiate abstract class: {cls.__name__}"
            )
        return super().__new__(cls)

    def __init_subclass__(
            cls,
            custom_types: collections.abc.Mapping[
                    str, collections.abc.Callable[[str], object]
            ] = {},
            **kwargs: typing.Any
    ) -> None:
        """Mutate subclasses.
        """
        cls.__parser = argparse.ArgumentParser(**kwargs)
        for name, factory in custom_types.items():
            cls.__parser.register("type", name, factory)
        arguments: dict[str, _Argument[object]] = {}
        groups: dict[str, _Group] = {}
        mxgroups: dict[str, _MXGroup] = {}
        for name, item in list(vars(cls).items()):
            if (
                name.startswith("_Arguments__")
                or re.match(r"^__[a-zA-Z0-9_]+__$", name)
            ):
                continue
            if not isinstance(item, _ConfigItem):
                raise TypeError(
                    f"Non-argument attribute: {cls.__name__}.{name}"
                )
            if isinstance(item, _Argument):
                arguments[name] = item
            elif isinstance(item, _Group):
                groups[name] = item
            elif isinstance(item, _MXGroup):
                mxgroups[name] = item
            else:
                assert False
        cls.__ap_groups = {}
        cls.__process_groups(groups)
        cls.__process_mxgroups(mxgroups)
        cls.__process_args(arguments)

    @classmethod
    def __process_groups(cls, groups: dict[str, _Group]) -> None:
        for name, grp in groups.items():
            apg = cls.__parser.add_argument_group(grp.title, grp.description)
            grp.arg_group = apg
            cls.__ap_groups[name] = apg
            delattr(cls, name)
        cls.__arg_groups = groups

    @classmethod
    def __process_mxgroups(cls, mxgroups: dict[str, _MXGroup]) -> None:
        for name, mxgrp in mxgroups.items():
            #assert name not in cls.__ap_groups
            if mxgrp.group is not None:
                ac: argparse._ActionsContainer = cls.__ap_groups[mxgrp.group]
            else:
                ac = cls.__parser
            apmxg = ac.add_mutually_exclusive_group(required=mxgrp.required)
            mxgrp.mx_group = apmxg
            cls.__ap_groups[name] = apmxg
            delattr(cls, name)
        cls.__mx_groups = mxgroups

    @classmethod
    def __process_args(cls, arguments: dict[str, _Argument[object]]) -> None:
        type_hints = typing.get_type_hints(cls)
        for dest, argument in arguments.items():
            argument._type_hint = type_hints[dest]
            if argument.type is None:
                argument._factory = _resolve_type(
                    argument._type_hint, argument.sentinel
                )
            else:
                argument._factory = argument.type
            if argument.group is not None:
                ac: argparse._ActionsContainer = cls.__ap_groups[argument.group]
            else:
                ac = cls.__parser
            if argument.positional:
                _add_positional(ac, dest, argument)
            else:
                _add_flag(ac, dest, argument)
            delattr(cls, dest)
        cls.__arguments = arguments

    @classmethod
    def parse(
            cls, args: collections.abc.Sequence[str] | None=None
    ) -> typing.Self:
        ns = cls.__parser.parse_args(args)
        parsed = cls()
        for name in cls.__arguments.keys():
            setattr(parsed, name, getattr(ns, name))
        return parsed

    def __repr__(self) -> str:
        arguments: list[str] = []
        for name in self.__arguments.keys():
            arguments.append(f"{name}: {getattr(self, name)}")
        return (
            f"<{self.__class__.__module__}.{self.__class__.__qualname__} {{"
            f"{", ".join(arguments)}}}>"
        )



# kate: tab-width 8; indent-width 4; replace-tabs on;
