"""
Test decorators for Requete.

This module provides decorators to define tests for pipeline nodes. Tests are
integrated into the pipeline execution and help ensure data quality at various
stages.

Test Types:
    - unit: Isolated tests that run with a SparkSession (no real data)
    - integration: Tests that validate actual node output after execution
    - promotion: Required tests that must pass before promote nodes execute
    - source: Tests that validate source node output data quality

Example:
    >>> from requete import tests
    >>> from pyspark.sql import SparkSession, DataFrame
    >>>
    >>> @tests.unit(tag="transform_users")
    ... def test_transform_logic(spark: SparkSession) -> None:
    ...     # Create test data and verify transform logic
    ...     test_df = spark.createDataFrame([("alice", 25)], ["name", "age"])
    ...     assert test_df.count() == 1
    >>>
    >>> @tests.promotion(tag="promote_analytics", env=["prod"])
    ... def test_before_promote(daily_metrics_df: DataFrame) -> None:
    ...     assert daily_metrics_df.count() > 0
    ...     assert "revenue" in daily_metrics_df.columns
"""

from typing import Callable, TypeVar

F = TypeVar("F", bound=Callable[..., object])


def unit(tag: str):
    """
    Mark a function as a unit test.

    Unit tests are isolated tests that verify node logic without running the
    actual pipeline. They receive a SparkSession to create test data and
    validate transformations in isolation.

    Args:
        tag: The tag of the node being tested. Must reference an existing
            node in the pipeline.

    Returns:
        A decorator that marks the function as a unit test.

    Example:
        >>> @tests.unit(tag="clean_users")
        ... def test_removes_nulls(spark: SparkSession) -> None:
        ...     # Create test data with nulls
        ...     test_df = spark.createDataFrame(
        ...         [("alice", 25), (None, 30), ("bob", None)],
        ...         ["name", "age"]
        ...     )
        ...     # Import and test the transform function
        ...     from my_pipeline.transforms import clean_users
        ...     result = clean_users(test_df)
        ...     assert result.filter("name IS NULL OR age IS NULL").count() == 0

    Note:
        - Function must accept exactly one parameter: ``spark: SparkSession``
        - Function must return ``None``
        - Tests should use assertions to validate expected behavior
        - Unit tests are environment-agnostic (no ``env`` parameter)
    """

    def decorator(func: F) -> F:
        return func

    return decorator


def integration(tag: str, env: list[str]):
    """
    Mark a function as an integration test.

    Integration tests validate the actual output of a node after it has been
    executed in a specific environment. They receive the DataFrame produced
    by the node and perform assertions on the real data.

    Args:
        tag: The tag of the node being tested. Must reference an existing
            node in the pipeline.
        env: List of environments where this test should run.

    Returns:
        A decorator that marks the function as an integration test.

    Example:
        >>> @tests.integration(tag="daily_metrics", env=["dev", "staging"])
        ... def test_metrics_positive(daily_metrics_df: DataFrame) -> None:
        ...     # Verify no negative revenue values
        ...     negative_count = daily_metrics_df.filter("revenue < 0").count()
        ...     assert negative_count == 0, f"Found {negative_count} negative revenue rows"
        ...
        ...     # Verify expected columns exist
        ...     required_cols = ["date", "revenue", "users"]
        ...     for col in required_cols:
        ...         assert col in daily_metrics_df.columns

    Note:
        - Function must accept exactly one parameter: ``{node_tag}_df: DataFrame``
        - Parameter name must be the node tag with ``_df`` suffix
        - Function must return ``None``
        - Tests run after the node executes and receive the actual output
    """

    def decorator(func: F) -> F:
        return func

    return decorator


def promotion(tag: str, env: list[str]):
    """
    Mark a function as a promotion test.

    Promotion tests are required validation tests that must pass before a
    promote node can execute. They receive the same input data that the
    promote node will receive and act as a data quality gate.

    Args:
        tag: The tag of the promote node being tested. Must reference an
            existing promote node in the pipeline.
        env: List of environments where this test should run. Must cover
            all environments where the promote node is defined.

    Returns:
        A decorator that marks the function as a promotion test.

    Example:
        >>> @tests.promotion(tag="promote_analytics", env=["prod"])
        ... def test_data_quality(daily_metrics_df: DataFrame) -> None:
        ...     # Ensure minimum data volume
        ...     row_count = daily_metrics_df.count()
        ...     assert row_count >= 1000, f"Expected >= 1000 rows, got {row_count}"
        ...
        ...     # Ensure no nulls in critical columns
        ...     null_count = daily_metrics_df.filter("user_id IS NULL").count()
        ...     assert null_count == 0, f"Found {null_count} null user_ids"

    Note:
        - Every promote node must have at least one promotion test
        - Function parameters must match the promote node's dependencies
          (named ``{dependency_tag}_df``)
        - Function must return ``None``
        - If the test fails (raises an exception), the promote node will not run
        - Test environments must cover all promote node environments

    See Also:
        :func:`requete.nodes.promote`: Define promote nodes that require these tests
    """

    def decorator(func: F) -> F:
        return func

    return decorator


def source(tag: str, env: list[str]):
    """
    Mark a function as a source test.

    Source tests validate the output of source nodes to ensure data quality
    at the point of ingestion. They receive the DataFrame produced by the
    source node and perform assertions on schema, data types, and values.

    Args:
        tag: The tag of the source node being tested. Must reference an
            existing source node in the pipeline.
        env: List of environments where this test should run.

    Returns:
        A decorator that marks the function as a source test.

    Example:
        >>> @tests.source(tag="users", env=["dev", "prod"])
        ... def test_users_schema(users_df: DataFrame) -> None:
        ...     # Verify required columns exist
        ...     required_cols = ["user_id", "email", "created_at"]
        ...     for col in required_cols:
        ...         assert col in users_df.columns, f"Missing column: {col}"
        ...
        ...     # Verify no duplicate user_ids
        ...     total = users_df.count()
        ...     distinct = users_df.select("user_id").distinct().count()
        ...     assert total == distinct, f"Found {total - distinct} duplicate user_ids"

    Note:
        - Function must accept exactly one parameter: ``{source_tag}_df: DataFrame``
        - Parameter name must be the source tag with ``_df`` suffix
        - Function must return ``None``
        - Tests run after the source node executes and receive the actual output
    """

    def decorator(func: F) -> F:
        return func

    return decorator
