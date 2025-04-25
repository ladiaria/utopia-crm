# This file contains helper functions for ORM queries to optimize performance in queries and templates.


def get_latest_from_prefetch(obj, related_name, sort_field="id", to_attr=None):
    """
    Returns the latest object from a prefetched related set, falling back to a DB query if not prefetched.
    This is used in the case we want to get the latest object from a related set without doing a new query, for example
    in a template, when we call for the latest related object of the instance we're working with.

    Args:
        obj: The instance with a related set.
        related_name (str): The name of the related manager (e.g., 'activity_set').
        sort_field (str): The field to sort by when determining the latest object (default is 'id').
        to_attr (str): The attribute to set the latest object on (optional).

    Returns:
        The latest related object or None.
    """
    if to_attr:
        items = getattr(obj, to_attr, None)
        if items:
            return max(items, key=lambda o: getattr(o, sort_field))
        return None

    if hasattr(obj, "_prefetched_objects_cache") and related_name in obj._prefetched_objects_cache:
        items = obj._prefetched_objects_cache[related_name]
        if items:
            return max(items, key=lambda o: getattr(o, sort_field))
        return None

    manager = getattr(obj, related_name, None)
    if manager is not None:
        return manager.order_by(f"-{sort_field}").first()

    return None


def get_first_from_prefetch(obj, related_name, sort_field="id", to_attr=None):
    """
    Returns the first object from a prefetched related set (e.g., earliest),
    falling back to a DB query if not prefetched.

    Args:
        obj: The instance with a related set.
        related_name (str): The name of the related manager (e.g., 'activity_set').
        sort_field (str): The field to sort by when determining the first object (default is 'id').
        to_attr (str): The attribute to set the first object on (optional).

    Returns:
        The first related object or None.
    """
    if to_attr:
        items = getattr(obj, to_attr, None)
        if items:
            return min(items, key=lambda o: getattr(o, sort_field))
        return None

    if hasattr(obj, "_prefetched_objects_cache") and related_name in obj._prefetched_objects_cache:
        items = obj._prefetched_objects_cache[related_name]
        if items:
            return min(items, key=lambda o: getattr(o, sort_field))
        return None

    manager = getattr(obj, related_name, None)
    if manager is not None:
        return manager.order_by(sort_field).first()

    return None


def get_all_from_prefetch(obj, related_name, to_attr=None):
    """
    Returns all related objects from a prefetched set if available, or falls back to a normal queryset.

    Args:
        obj: The instance with a related set.
        related_name (str): The name of the related manager (e.g., 'activity_set').
        to_attr (str): The attribute to set the related objects on (optional).

    Returns:
        A list of related objects or an empty list.
    """
    if to_attr:
        return getattr(obj, to_attr, [])

    if hasattr(obj, "_prefetched_objects_cache") and related_name in obj._prefetched_objects_cache:
        return obj._prefetched_objects_cache[related_name]

    manager = getattr(obj, related_name, None)
    if manager is not None:
        return manager.all()

    return []


def get_filtered_from_prefetch(obj, related_name, filter_func, to_attr=None):
    """
    Returns filtered related objects using a callable filter function.
    Only uses prefetched data if available.

    Args:
        obj: The instance with a related set.
        related_name (str): The name of the related manager (e.g., 'activity_set').
        filter_func (callable): A callable that takes an object and returns a boolean.
        to_attr (str): The attribute to set the filtered objects on (optional).

    Example call:
        get_filtered_from_prefetch(obj, 'activity_set', lambda x: x.type == 'email')

    Returns:
        A list of filtered related objects or an empty list.
    """
    if to_attr:
        items = getattr(obj, to_attr, [])
    elif hasattr(obj, "_prefetched_objects_cache") and related_name in obj._prefetched_objects_cache:
        items = obj._prefetched_objects_cache[related_name]
    else:
        manager = getattr(obj, related_name, None)
        return manager.filter(filter_func) if manager else []

    return list(filter(filter_func, items))
