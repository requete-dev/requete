"""
Session decorator for Requete.

This module provides the session decorator to define engine connection nodes.
Session nodes create and configure the execution engine (Spark, DuckDB, Snowflake)
that powers the data pipeline.

Each pipeline requires at least one session node per engine/environment combination.
The session provides the execution context for all other nodes in that environment.

Example:
    >>> from requete import sessions
    >>> from pyspark.sql import SparkSession
    >>>
    >>> @sessions.session(
    ...     tag="spark_session",
    ...     pipeline="analytics",
    ...     engine="spark",
    ...     env=["dev", "prod"]
    ... )
    ... def create_spark_session() -> SparkSession:
    ...     return (
    ...         SparkSession.builder
    ...         .appName("analytics")
    ...         .getOrCreate()
    ...     )
"""

from typing import Callable, List, TypeVar

F = TypeVar("F", bound=Callable)


def session(tag: str, pipeline: str, engine: str, env: List[str]):
    """
    Mark a function as a session node.

    Session nodes create the execution engine connection used by all other nodes
    in the pipeline. They are the foundation of pipeline execution and must be
    defined for each engine/environment combination.

    Args:
        tag: Unique identifier for this session within the pipeline. Session tags
            must be unique per pipeline regardless of engine or environment.
        pipeline: Name of the pipeline this session belongs to.
        engine: The execution engine type. Supported values:

            - ``"spark"``: Apache Spark (uses ``pyspark.sql.SparkSession``)
            - ``"duckdb"``: DuckDB (uses ``duckdb.experimental.spark.sql.SparkSession``)
            - ``"snowflake"``: Snowflake (uses ``snowflake.snowpark.Session``)

        env: List of environments where this session should be created
            (e.g., ["dev", "prod"]).

    Returns:
        A decorator that marks the function as a session node.

    Example:
        >>> # Spark session for dev and prod
        >>> @sessions.session(
        ...     tag="spark_session",
        ...     pipeline="analytics",
        ...     engine="spark",
        ...     env=["dev", "prod"]
        ... )
        ... def create_spark() -> SparkSession:
        ...     return SparkSession.builder.appName("analytics").getOrCreate()

        >>> # DuckDB session for local development
        >>> @sessions.session(
        ...     tag="duckdb_session",
        ...     pipeline="analytics",
        ...     engine="duckdb",
        ...     env=["local"]
        ... )
        ... def create_duckdb() -> SparkSession:
        ...     from duckdb.experimental.spark.sql import SparkSession
        ...     return SparkSession.builder.getOrCreate()

    Note:
        - Function must accept no parameters
        - Function must return the appropriate session type for the engine:

          - ``spark``: Return ``pyspark.sql.SparkSession``
          - ``duckdb``: Return ``duckdb.experimental.spark.sql.SparkSession``
          - ``snowflake``: Return ``snowflake.snowpark.Session``

        - Session tags must be unique within a pipeline (across all engines/envs)
        - Each file should contain sessions for only one engine type
    """

    def decorator(func: F) -> F:
        return func

    return decorator
