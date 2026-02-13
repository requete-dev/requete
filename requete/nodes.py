"""
Pipeline node decorators for Requete.

This module provides decorators to define data pipeline nodes. Each decorator
marks a function as a specific type of node in the pipeline DAG (Directed
Acyclic Graph).

Node Types:
    - source: Reads data from external systems
    - backfill_source: Reads historical data for backfill operations
    - transform: Transforms data from upstream dependencies
    - sink: Writes data to external systems
    - promote: Writes data after validation tests pass

Example:
    >>> from requete import nodes
    >>> from pyspark.sql import SparkSession, DataFrame
    >>>
    >>> @nodes.source(tag="users", pipeline="analytics", env=["dev", "prod"])
    ... def load_users(spark: SparkSession) -> DataFrame:
    ...     return spark.read.parquet("s3://bucket/users")
    >>>
    >>> @nodes.transform(tag="active_users", pipeline="analytics", depends_on=["users"])
    ... def filter_active(users_df: DataFrame) -> DataFrame:
    ...     return users_df.filter("is_active = true")
"""

from typing import Callable, TypeVar

F = TypeVar("F", bound=Callable[..., object])


def source(tag: str, pipeline: str, env: list[str]):
    """
    Mark a function as a data source node.

    Source nodes are entry points to a pipeline that read data from external
    systems (databases, files, APIs, etc.). They have no upstream dependencies
    and produce a DataFrame as output.

    Args:
        tag: Unique identifier for this node within the pipeline. Must be
            descriptive and at least 3 characters long.
        pipeline: Name of the pipeline this node belongs to.
        env: List of environments where this source should run
            (e.g., ["dev", "prod"]).

    Returns:
        A decorator that marks the function as a source node.

    Example:
        >>> @nodes.source(tag="orders", pipeline="ecommerce", env=["dev", "prod"])
        ... def load_orders(spark: SparkSession) -> DataFrame:
        ...     return spark.read.parquet("s3://data/orders")

    Note:
        - Function must accept exactly one parameter: ``spark: SparkSession``
        - Function must return a ``DataFrame``
        - The ``env`` list must cover all environments defined in session nodes
    """

    def decorator(func: F) -> F:
        return func

    return decorator


def backfill_source(tag: str, pipeline: str, env: list[str]):
    """
    Mark a function as a backfill source node.

    Backfill sources are similar to regular sources but are used specifically
    for historical data loading during backfill operations. They receive an
    additional context parameter containing backfill metadata (date ranges, etc.).

    Args:
        tag: Unique identifier for this node within the pipeline. Should match
            the corresponding regular source tag.
        pipeline: Name of the pipeline this node belongs to.
        env: List of environments where this backfill source should run
            (typically ["backfill"]).

    Returns:
        A decorator that marks the function as a backfill source node.

    Example:
        >>> @nodes.backfill_source(tag="orders", pipeline="ecommerce", env=["backfill"])
        ... def load_orders_backfill(spark: SparkSession, context: dict) -> DataFrame:
        ...     from_date = context.get("from_date")
        ...     to_date = context.get("to_date")
        ...     return spark.read.parquet("s3://data/orders").filter(
        ...         f"order_date BETWEEN '{from_date}' AND '{to_date}'"
        ...     )

    Note:
        - Function must accept two parameters: ``spark: SparkSession`` and
          ``context: dict``
        - Function must return a ``DataFrame``
        - The context dict contains backfill parameters like date ranges
    """

    def decorator(func: F) -> F:
        return func

    return decorator


def transform(tag: str, pipeline: str, depends_on: list[str]):
    """
    Mark a function as a transform node.

    Transform nodes process data from one or more upstream dependencies and
    produce a new DataFrame. They are environment-agnostic and run wherever
    their dependencies run.

    Args:
        tag: Unique identifier for this node within the pipeline.
        pipeline: Name of the pipeline this node belongs to.
        depends_on: List of upstream node tags that this transform depends on.
            The order determines the function parameter order.

    Returns:
        A decorator that marks the function as a transform node.

    Example:
        >>> @nodes.transform(
        ...     tag="user_orders",
        ...     pipeline="ecommerce",
        ...     depends_on=["users", "orders"]
        ... )
        ... def join_user_orders(users_df: DataFrame, orders_df: DataFrame) -> DataFrame:
        ...     return users_df.join(orders_df, "user_id")

    Note:
        - Function parameters must be named ``{dependency_tag}_df`` in the same
          order as ``depends_on``
        - All parameters must be typed as ``DataFrame``
        - Function must return a ``DataFrame``
        - Transform nodes cannot have an ``env`` parameter
    """

    def decorator(func: F) -> F:
        return func

    return decorator


def sink(tag: str, pipeline: str, env: list[str], depends_on: list[str]):
    """
    Mark a function as a sink node.

    Sink nodes write data to external systems (databases, files, etc.). They
    consume data from upstream dependencies and do not produce output for
    downstream nodes.

    Args:
        tag: Unique identifier for this node within the pipeline.
        pipeline: Name of the pipeline this node belongs to.
        env: List of environments where this sink should run.
        depends_on: List of upstream node tags that this sink depends on.

    Returns:
        A decorator that marks the function as a sink node.

    Example:
        >>> @nodes.sink(
        ...     tag="write_reports",
        ...     pipeline="analytics",
        ...     env=["prod"],
        ...     depends_on=["daily_metrics"]
        ... )
        ... def write_reports(daily_metrics_df: DataFrame) -> None:
        ...     daily_metrics_df.write.mode("overwrite").saveAsTable("reports")

    Note:
        - Function parameters must be named ``{dependency_tag}_df``
        - All parameters must be typed as ``DataFrame``
        - Function must return ``None``
    """

    def decorator(func: F) -> F:
        return func

    return decorator


def promote(tag: str, pipeline: str, env: list[str], depends_on: list[str]):
    """
    Mark a function as a promote node.

    Promote nodes are similar to sink nodes but include a validation step.
    Before the promote function executes, associated promotion tests must pass.
    This ensures data quality before writing to production systems.

    Args:
        tag: Unique identifier for this node within the pipeline.
        pipeline: Name of the pipeline this node belongs to.
        env: List of environments where this promote should run.
        depends_on: List of upstream node tags that this promote depends on.

    Returns:
        A decorator that marks the function as a promote node.

    Example:
        >>> @nodes.promote(
        ...     tag="promote_analytics",
        ...     pipeline="analytics",
        ...     env=["prod"],
        ...     depends_on=["daily_metrics"]
        ... )
        ... def promote_analytics(daily_metrics_df: DataFrame) -> None:
        ...     daily_metrics_df.write.mode("overwrite").saveAsTable("analytics_prod")

    Note:
        - Requires a corresponding ``@tests.promotion`` test with the same tag
        - Promotion tests run before this function and must pass
        - Function parameters must be named ``{dependency_tag}_df``
        - Function must return ``None``

    See Also:
        :func:`requete.tests.promotion`: Define validation tests for promote nodes
    """

    def decorator(func: F) -> F:
        return func

    return decorator
