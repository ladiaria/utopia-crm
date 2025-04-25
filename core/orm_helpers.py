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
