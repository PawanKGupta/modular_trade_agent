"""
Dependency Injection Container

Simple DI container for managing application dependencies.
This promotes loose coupling and makes testing easier.
"""

from typing import Dict, Callable, Any, TypeVar, Type
from functools import lru_cache


T = TypeVar('T')


class DependencyContainer:
    """
    Simple dependency injection container
    
    Manages creation and lifecycle of application dependencies.
    Supports both singleton and factory patterns.
    """
    
    def __init__(self):
        self._singletons: Dict[Type, Any] = {}
        self._factories: Dict[Type, Callable[[], Any]] = {}
    
    def register_singleton(self, interface: Type[T], instance: T):
        """
        Register a singleton instance
        
        Args:
            interface: Interface or class type
            instance: Concrete implementation instance
        """
        self._singletons[interface] = instance
    
    def register_factory(self, interface: Type[T], factory: Callable[[], T]):
        """
        Register a factory function
        
        Args:
            interface: Interface or class type
            factory: Function that creates instances
        """
        self._factories[interface] = factory
    
    def get(self, interface: Type[T]) -> T:
        """
        Get an instance of the requested type
        
        Args:
            interface: Interface or class type to resolve
            
        Returns:
            Instance of the requested type
            
        Raises:
            KeyError: If type is not registered
        """
        # Check singletons first
        if interface in self._singletons:
            return self._singletons[interface]
        
        # Check factories
        if interface in self._factories:
            return self._factories[interface]()
        
        raise KeyError(f"No registration found for {interface.__name__}")
    
    def has(self, interface: Type) -> bool:
        """Check if type is registered"""
        return interface in self._singletons or interface in self._factories
    
    def clear(self):
        """Clear all registrations (useful for testing)"""
        self._singletons.clear()
        self._factories.clear()


# Global container instance
_container = DependencyContainer()


def get_container() -> DependencyContainer:
    """Get the global dependency container"""
    return _container


def reset_container():
    """Reset the global container (for testing)"""
    global _container
    _container = DependencyContainer()


# Convenience functions
def register_singleton(interface: Type[T], instance: T):
    """Register a singleton in the global container"""
    _container.register_singleton(interface, instance)


def register_factory(interface: Type[T], factory: Callable[[], T]):
    """Register a factory in the global container"""
    _container.register_factory(interface, factory)


def resolve(interface: Type[T]) -> T:
    """Resolve an instance from the global container"""
    return _container.get(interface)


def has_registration(interface: Type) -> bool:
    """Check if type is registered in global container"""
    return _container.has(interface)
