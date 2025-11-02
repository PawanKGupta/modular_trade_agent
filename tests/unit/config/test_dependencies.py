import pytest

from src.config.dependencies import (
    DependencyContainer,
    register_singleton,
    register_factory,
    resolve,
    has_registration,
    reset_container,
    get_container,
)


class IFoo: ...
class Foo(IFoo):
    def __init__(self, x):
        self.x = x


def test_dependency_container_singleton_and_factory():
    c = DependencyContainer()

    foo_singleton = Foo(1)
    c.register_singleton(IFoo, foo_singleton)
    assert c.get(IFoo) is foo_singleton
    assert c.has(IFoo)

    class IBar: ...
    class Bar(IBar):
        pass

    c.register_factory(IBar, lambda: Bar())
    b1 = c.get(IBar)
    b2 = c.get(IBar)
    assert isinstance(b1, Bar) and isinstance(b2, Bar)
    assert b1 is not b2  # factory creates new instances

    c.clear()
    assert not c.has(IFoo)


def test_global_container_helpers():
    reset_container()

    foo = Foo(2)
    register_singleton(IFoo, foo)
    assert has_registration(IFoo)
    assert resolve(IFoo) is foo

    # Register factory and resolve
    class IBaz: ...
    class Baz(IBaz):
        pass

    register_factory(IBaz, lambda: Baz())
    assert isinstance(resolve(IBaz), Baz)
