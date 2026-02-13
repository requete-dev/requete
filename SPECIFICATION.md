# Requete Python Library Specification

**Version:** 0.1.0  
**Last Updated:** January 2025

## Table of Contents

1. [Overview](#overview)
2. [Core Concepts](#core-concepts)
3. [Node Types](#node-types)
4. [Test Types](#test-types)
5. [Environment System](#environment-system)
6. [Examples](#examples)

---

## Overview

The Requete Python library provides decorators for defining data pipeline nodes. These decorators are **metadata markers only** — they don't execute any logic themselves. The Requete orchestrator (Rust/LSP) reads these decorators to build the DAG, validate dependencies, and generate execution artifacts.

### Design Philosophy

- **Pure Functions**: All transform nodes must be pure functions (same input → same output)
- **Explicit Dependencies**: All dependencies declared via `depends_on` parameter
- **Environment Isolation**: Different implementations per environment (dev/staging/prod)
- **Engine Agnostic**: Write once in PySpark API, run on DuckDB/Spark/Snowflake

---

## Core Concepts

### DAG (Directed Acyclic Graph)

Pipelines are defined as DAGs where:

- **Nodes** are Python functions decorated with `@nodes.*` or `@tests.*`
- **Edges** are defined by `depends_on` parameters
- **Execution order** is determined by topological sort

### Tags

Every node has a unique `tag` identifier. Tags are used to:

- Reference nodes in `depends_on` lists
- Associate tests with nodes
- Generate artifacts and lineage graphs

**Rules:**

- Tags must be unique within a node type + environment combination
- Tags should be descriptive (e.g., `"users_cleaned"` not `"node1"`)
- Same tag across environments implies same logical operation

### Environments

Environments represent different execution contexts:

- `dev`: Local development with mock data
- `staging`: Pre-production testing
- `prod`: Production execution
- `backfill`: Historical data processing
- Custom: Any user-defined environment name

---

## Node Types

### 1. Session Nodes

**Purpose:** Create database/engine connections.

**Decorator:**

```python
@sessions.session(tag: str, pipeline: str, engine: str, env: List[str])
```

**Parameters:**

- `tag`: Unique identifier for this session
- `pipeline`: Name of the pipeline this session belongs to
- `engine`: Engine type (`"spark"`, `"duckdb"`, `"snowflake"`, etc.)
- `env`: List of environments this session applies to

**Return Type:** `SparkSession` (or engine-specific session object)

**Example:**

```python
from requete import sessions

@sessions.session(tag="dev_node", pipeline="analytics", engine="spark", env=["dev"])
def dev_session() -> SparkSession:
    """Creates local Spark session for development."""
    return SparkSession.builder.master("local[*]").getOrCreate()

@sessions.session(tag="prod_node", pipeline="analytics", engine="duckdb", env=["prod"])
def prod_session() -> SparkSession:
    """Creates MotherDuck connection for production."""
    return SparkSession.builder.remote("md:prod_db").getOrCreate()
```

**Notes:**

- Each `(engine, env)` combination requires a session node
- Session nodes define connection strings, configs, and credentials
- UI dropdown is populated from available session nodes

---

### 2. Source Nodes

**Purpose:** Read input data from external systems.

**Decorator:**

```python
@nodes.source(tag: str, pipeline: str, env: List[str])
```

**Parameters:**

- `tag`: Unique identifier for this data source
- `pipeline`: Name of the pipeline this source belongs to
- `env`: List of environments this source applies to

**Function Signature:**

```python
def source_function(sparkSession: SparkSession) -> DataFrame:
    ...
```

**Example:**

```python
@nodes.source(tag="customers", pipeline="analytics", env=["dev"])
def customers_dev(sparkSession: SparkSession) -> DataFrame:
    """Loads mock customer data for development."""
    schema = StructType([
        StructField("id", IntegerType(), True),
        StructField("name", StringType(), True)
    ])
    data = [(1, "Alice"), (2, "Bob")]
    return sparkSession.createDataFrame(data, schema)

@nodes.source(tag="customers", pipeline="analytics", env=["prod"])
def customers_prod(sparkSession: SparkSession) -> DataFrame:
    """Loads customer data from production table."""
    return sparkSession.table("prod.customers")
```

**Notes:**

- Use explicit schemas for mock data (cross-engine compatibility)
- Same tag across environments implies same logical dataset
- Sources have no dependencies (DAG entry points)

---

### 3. Backfill Source Nodes

**Purpose:** Read historical data for backfill operations.

**Decorator:**

```python
@nodes.backfill_source(tag: str, pipeline: str, env: List[str])
```

**Parameters:**

- `tag`: Unique identifier (typically same as regular source)
- `pipeline`: Name of the pipeline this backfill source belongs to
- `env`: List of environments (usually `["backfill"]`)

**Function Signature:**

```python
def backfill_function(sparkSession: SparkSession, context: dict[str, str]) -> DataFrame:
    ...
```

**Context Dictionary:**

- `from_date`: Start date for backfill (passed via CLI)
- `to_date`: End date for backfill (passed via CLI)
- Custom keys: Any additional CLI arguments

**Example:**

```python
@nodes.backfill_source(tag="events", pipeline="analytics", env=["backfill"])
def events_backfill(sparkSession: SparkSession, context: dict[str, str]) -> DataFrame:
    """Loads historical events for backfill period."""
    start = context['from_date']
    end = context['to_date']
    return sparkSession.table("events").filter(
        (col("event_date") >= start) & (col("event_date") < end)
    )
```

---

### 4. Transform Nodes

**Purpose:** Transform DataFrames using pure functions.

**Decorator:**

```python
@nodes.transform(tag: str, pipeline: str, depends_on: List[str])
```

**Parameters:**

- `tag`: Unique identifier for this transformation
- `pipeline`: Name of the pipeline this transform belongs to
- `depends_on`: List of upstream node tags (order matters!)

**Function Signature:**

```python
def transform_function(input1_df: DataFrame, input2_df: DataFrame, ...) -> DataFrame:
    ...
```

**Example:**

```python
@nodes.transform(tag="users_cleaned", pipeline="analytics", depends_on=["raw_users"])
def clean_users(raw_users_df: DataFrame) -> DataFrame:
    """Removes test users and normalizes names."""
    return raw_users_df.filter(col("email").contains("@")) \
                       .withColumn("name", upper(col("name")))

@nodes.transform(tag="joined_data", pipeline="analytics", depends_on=["users_cleaned", "orders"])
def join_data(users_cleaned_df: DataFrame, orders_df: DataFrame) -> DataFrame:
    """Joins users with their orders."""
    return users_cleaned_df.join(orders_df, on="user_id", how="inner")
```

**Rules:**

- **Must be pure functions**: Same input → same output, no side effects
- **No `env` parameter**: Transforms are environment-agnostic
- **Parameter naming**: Must be `{dependency_tag}_df` in the same order as `depends_on`
- **No I/O**: Don't read/write data inside transforms

---

### 5. Sink Nodes

**Purpose:** Write output data to external systems.

**Decorator:**

```python
@nodes.sink(tag: str, pipeline: str, env: List[str], depends_on: List[str])
```

**Parameters:**

- `tag`: Unique identifier for this sink
- `pipeline`: Name of the pipeline this sink belongs to
- `env`: List of environments this sink applies to
- `depends_on`: List of upstream node tags

**Function Signature:**

```python
def sink_function(input1_df: DataFrame, input2_df: DataFrame, ...) -> None:
    ...
```

**Example:**

```python
@nodes.sink(tag="write_results", pipeline="analytics", depends_on=["aggregated"], env=["dev"])
def write_dev(aggregated_df: DataFrame) -> None:
    """Writes results to dev table."""
    aggregated_df.write.mode("overwrite").saveAsTable("dev_results")

@nodes.sink(tag="write_results", pipeline="analytics", depends_on=["aggregated"], env=["prod"])
def write_prod(aggregated_df: DataFrame) -> None:
    """Writes results to production table."""
    aggregated_df.write.mode("append").saveAsTable("prod.results")
```

**Notes:**

- Sinks always execute (no conditional logic)
- Use for checkpointing, debugging, or unconditional writes
- For conditional writes, use `@nodes.promote()` instead

---

### 6. Promote Nodes

**Purpose:** Write data conditionally after test validation.

**Decorator:**

```python
@nodes.promote(tag: str, pipeline: str, env: List[str], depends_on: List[str])
```

**Parameters:**

- `tag`: Unique identifier for this promotion
- `pipeline`: Name of the pipeline this promote belongs to
- `env`: List of environments this promotion applies to
- `depends_on`: List of upstream node tags

**Function Signature:**

```python
def promote_function(input1_df: DataFrame, input2_df: DataFrame, ...) -> None:
    ...
```

**Example:**

```python
@nodes.promote(tag="promote_results", pipeline="analytics", depends_on=["aggregated"], env=["prod"])
def promote_prod(aggregated_df: DataFrame) -> None:
    """Promotes validated results to production promoted table."""
    aggregated_df.write.saveAsTable("prod.results_promoted")
```

**Rules:**

- **Requires promotion test**: Must have `@tests.promotion()` with same tag
- **Conditional execution**: Only runs if promotion test passes
- **Typically depends on transforms**: Not sinks (to avoid validating post-write data)

**Pattern: Sink + Promote**

```python
# Always write raw data
@nodes.sink(tag="write_raw", pipeline="analytics", depends_on=["transform"], env=["prod"])
def write_raw(transform_df: DataFrame) -> None:
    transform_df.write.saveAsTable("raw_results")

# Conditionally promote validated data
@nodes.promote(tag="promote", pipeline="analytics", depends_on=["transform"], env=["prod"])
def promote_validated(transform_df: DataFrame) -> None:
    transform_df.write.saveAsTable("promoted_results")
```

This ensures raw data is available for debugging even if promotion fails.

---

## Test Types

### 1. Unit Tests

**Purpose:** Test transformation logic with mock data, no external dependencies.

**Decorator:**

```python
@tests.unit(tag: str)
```

**Parameters:**

- `tag`: The transform node tag being tested

**Function Signature:**

```python
def test_function(sparkSession: SparkSession) -> None:
    ...
```

**Example:**

```python
@tests.unit(tag="calculate_revenue")
def test_revenue_calculation(sparkSession: SparkSession):
    """Tests revenue calculation with mock orders."""
    schema = StructType([
        StructField("price", IntegerType(), True),
        StructField("quantity", IntegerType(), True)
    ])
    orders = sparkSession.createDataFrame([(100, 2), (50, 1)], schema)

    result = calculate_revenue(orders)

    total = result.agg({"revenue": "sum"}).first()[0]
    assert total == 250, f"Expected 250, got {total}"
```

**Notes:**

- Run during development for fast feedback
- No `env` parameter (run in all environments)
- Should use small, synthetic mock data
- Test edge cases: nulls, empty DataFrames, boundary conditions

---

### 2. Integration Tests

**Purpose:** Test nodes with actual pipeline data in specific environments.

**Decorator:**

```python
@tests.integration(tag: str, env: List[str])
```

**Parameters:**

- `tag`: The node tag being tested
- `env`: List of environments to run this test

**Function Signature:**

```python
def test_function(node_tag_df: DataFrame) -> None:
    ...
```

**Example:**

```python
@tests.integration(tag="aggregated_users", env=["dev", "staging"])
def test_aggregation(aggregated_users_df: DataFrame):
    """Validates aggregation output in dev and staging."""
    assert aggregated_users_df.count() > 0, "Aggregation produced no rows"
    assert "total_revenue" in aggregated_users_df.columns

    # Check for nulls in critical columns
    null_count = aggregated_users_df.filter(col("total_revenue").isNull()).count()
    assert null_count == 0, f"Found {null_count} nulls in total_revenue"
```

**Notes:**

- Receives actual node output (not mock data)
- Can have different tests per environment
- Runs after node execution in the pipeline
- Good for data quality checks, schema validation

---

### 3. Promotion Tests

**Purpose:** Validate data before conditional promotion write.

**Decorator:**

```python
@tests.promotion(tag: str, env: List[str])
```

**Parameters:**

- `tag`: The promote node tag being tested
- `env`: List of environments to run this test

**Function Signature:**

```python
def test_function(dependency_tag_df: DataFrame) -> None:
    ...
```

**Example:**

```python
@tests.promotion(tag="promote_results", env=["prod"])
def test_promotion_prod(aggregated_df: DataFrame):
    """Validates results before production promotion."""
    assert aggregated_df.count() > 0, "Cannot promote empty dataset"

    # Business logic validation
    negative_revenue = aggregated_df.filter(col("revenue") < 0).count()
    assert negative_revenue == 0, "Found negative revenue values"

    # Completeness check
    null_users = aggregated_df.filter(col("user_id").isNull()).count()
    assert null_users == 0, "Found null user IDs"
```

**Rules:**

- **Required for promote nodes**: Every `@nodes.promote()` MUST have matching promotion test
- **Build fails without test**: Orchestrator validates at build time
- **Gates execution**: If test fails, promote node doesn't execute
- **Environment-specific**: Can have different validation per environment

---

## Environment System

### Environment Coverage Rules

**Rule 1: I/O nodes must cover all environments**

For each environment defined in session nodes, all I/O nodes (source, sink, promote) must provide implementations:

```python
# ✅ VALID: All I/O nodes cover dev, staging, prod
@sessions.session(tag="node", pipeline="p", engine="spark", env=["dev", "staging", "prod"])
@nodes.source(tag="data", pipeline="p", env=["dev", "staging", "prod"])
@nodes.sink(tag="write", pipeline="p", env=["dev", "staging", "prod"], depends_on=[...])
@nodes.promote(tag="promote", pipeline="p", env=["dev", "staging", "prod"], depends_on=[...])

# ❌ INVALID: Sink missing staging
@sessions.session(tag="node", pipeline="p", engine="spark", env=["dev", "staging", "prod"])
@nodes.source(tag="data", pipeline="p", env=["dev", "staging", "prod"])
@nodes.sink(tag="write", pipeline="p", env=["dev", "prod"], depends_on=[...])  # Missing staging!
```

**Rule 2: Transforms are environment-agnostic**

Transform nodes have no `env` parameter and run in all environments:

```python
# ✅ Transform runs wherever its dependencies run
@nodes.transform(tag="clean", pipeline="analytics", depends_on=["raw_data"])
def clean_data(raw_data_df: DataFrame) -> DataFrame:
    return raw_data_df.filter(col("status") == "active")
```

**Rule 3: Tests can be environment-specific**

Unit tests run everywhere, integration/promotion tests are environment-specific:

```python
# Runs in all environments
@tests.unit(tag="transform")
def test_transform(sparkSession: SparkSession):
    ...

# Only runs in dev and staging
@tests.integration(tag="transform", env=["dev", "staging"])
def test_integration(transform_df: DataFrame):
    ...
```

### Multi-Engine Support

Different engines can be used per environment:

```python
# duckdb.py - Use DuckDB for dev
@sessions.session(tag="dev_node", pipeline="analytics", engine="duckdb", env=["dev"])
def dev_session() -> SparkSession:
    return SparkSession.builder.remote("local").getOrCreate()

# spark.py - Use Spark for prod
@sessions.session(tag="prod_node", pipeline="analytics", engine="spark", env=["prod"])
def prod_session() -> SparkSession:
    return SparkSession.builder.master("spark://cluster:7077").getOrCreate()
```

**UI dropdown populated from code:**

- Orchestrator scans all session nodes
- Extracts `(engine, env)` combinations
- Populates dropdown with available options
- Users can only select valid combinations

---

## Examples

### Complete Pipeline Example

```python
# ============================================================================
# sessions/spark.py
# ============================================================================
from pyspark.sql import SparkSession
from requete import sessions

@sessions.session(tag="dev_node", pipeline="analytics", engine="spark", env=["dev"])
def dev_session() -> SparkSession:
    """Creates local Spark session for development."""
    return SparkSession.builder.master("local[*]").getOrCreate()

@sessions.session(tag="prod_node", pipeline="analytics", engine="spark", env=["prod"])
def prod_session() -> SparkSession:
    """Creates production Spark cluster connection."""
    return SparkSession.builder \
        .master("spark://prod-cluster:7077") \
        .config("spark.sql.warehouse.dir", "s3://prod-data/") \
        .getOrCreate()


# ============================================================================
# sources/users.py
# ============================================================================
from pyspark.sql import DataFrame, SparkSession
from pyspark.sql.types import StructType, StructField, IntegerType, StringType
from requete import nodes

@nodes.source(tag="raw_users", pipeline="analytics", env=["dev"])
def users_dev(sparkSession: SparkSession) -> DataFrame:
    """Mock user data for development."""
    schema = StructType([
        StructField("user_id", IntegerType(), True),
        StructField("name", StringType(), True),
        StructField("email", StringType(), True)
    ])
    data = [
        (1, "Alice", "alice@example.com"),
        (2, "Bob", "bob@example.com"),
        (3, "TestUser", "test@test.com")
    ]
    return sparkSession.createDataFrame(data, schema)

@nodes.source(tag="raw_users", pipeline="analytics", env=["prod"])
def users_prod(sparkSession: SparkSession) -> DataFrame:
    """Production user data."""
    return sparkSession.table("prod.users")


# ============================================================================
# sources/orders.py
# ============================================================================
from pyspark.sql import DataFrame, SparkSession
from pyspark.sql.types import StructType, StructField, IntegerType
from requete import nodes

@nodes.source(tag="raw_orders", pipeline="analytics", env=["dev"])
def orders_dev(sparkSession: SparkSession) -> DataFrame:
    """Mock order data for development."""
    schema = StructType([
        StructField("order_id", IntegerType(), True),
        StructField("user_id", IntegerType(), True),
        StructField("amount", IntegerType(), True)
    ])
    data = [(1, 1, 100), (2, 1, 200), (3, 2, 150)]
    return sparkSession.createDataFrame(data, schema)

@nodes.source(tag="raw_orders", pipeline="analytics", env=["prod"])
def orders_prod(sparkSession: SparkSession) -> DataFrame:
    """Production order data."""
    return sparkSession.table("prod.orders")


# ============================================================================
# transforms/clean_users.py
# ============================================================================
from pyspark.sql import DataFrame
from pyspark.sql.functions import col, upper
from requete import nodes, tests

@nodes.transform(tag="users_cleaned", pipeline="analytics", depends_on=["raw_users"])
def clean_users(raw_users_df: DataFrame) -> DataFrame:
    """Removes test users and normalizes data."""
    return raw_users_df.filter(~col("email").contains("test")) \
                       .withColumn("name", upper(col("name")))

@tests.unit(tag="users_cleaned")
def test_clean_users(sparkSession: SparkSession):
    """Tests user cleaning logic."""
    from pyspark.sql.types import StructType, StructField, IntegerType, StringType

    schema = StructType([
        StructField("user_id", IntegerType(), True),
        StructField("name", StringType(), True),
        StructField("email", StringType(), True)
    ])
    input_data = [
        (1, "alice", "alice@example.com"),
        (2, "bob", "test@test.com")
    ]
    raw_users_df = sparkSession.createDataFrame(input_data, schema)

    result = clean_users(raw_users_df)

    assert result.count() == 1, "Should filter out test users"
    assert result.first()["name"] == "ALICE", "Should uppercase names"


# ============================================================================
# transforms/user_revenue.py
# ============================================================================
from pyspark.sql import DataFrame
from pyspark.sql.functions import col, sum as spark_sum
from requete import nodes, tests

@nodes.transform(tag="user_revenue", pipeline="analytics", depends_on=["users_cleaned", "raw_orders"])
def calculate_revenue(users_cleaned_df: DataFrame, raw_orders_df: DataFrame) -> DataFrame:
    """Calculates total revenue per user."""
    return users_cleaned_df.join(raw_orders_df, on="user_id", how="inner") \
                           .groupBy("user_id", "name") \
                           .agg(spark_sum("amount").alias("total_revenue"))

@tests.unit(tag="user_revenue")
def test_revenue_calculation(sparkSession: SparkSession):
    """Tests revenue aggregation."""
    from pyspark.sql.types import StructType, StructField, IntegerType, StringType

    user_schema = StructType([
        StructField("user_id", IntegerType(), True),
        StructField("name", StringType(), True)
    ])
    users_cleaned_df = sparkSession.createDataFrame([(1, "Alice")], user_schema)

    order_schema = StructType([
        StructField("user_id", IntegerType(), True),
        StructField("amount", IntegerType(), True)
    ])
    raw_orders_df = sparkSession.createDataFrame([(1, 100), (1, 200)], order_schema)

    result = calculate_revenue(users_cleaned_df, raw_orders_df)

    assert result.count() == 1
    assert result.first()["total_revenue"] == 300

@tests.integration(tag="user_revenue", env=["dev"])
def test_revenue_dev(user_revenue_df: DataFrame):
    """Integration test for dev environment."""
    assert user_revenue_df.count() > 0, "Revenue data should not be empty"
    assert "total_revenue" in user_revenue_df.columns


# ============================================================================
# sinks/write_revenue.py
# ============================================================================
from pyspark.sql import DataFrame
from requete import nodes

@nodes.sink(tag="write_revenue", pipeline="analytics", depends_on=["user_revenue"], env=["dev"])
def write_dev(user_revenue_df: DataFrame) -> None:
    """Writes revenue to dev table."""
    user_revenue_df.write.mode("overwrite").saveAsTable("dev_user_revenue")

@nodes.sink(tag="write_revenue", pipeline="analytics", depends_on=["user_revenue"], env=["prod"])
def write_prod(user_revenue_df: DataFrame) -> None:
    """Writes revenue to production table."""
    user_revenue_df.write.mode("append").saveAsTable("prod.user_revenue")


# ============================================================================
# promotes/promote_revenue.py
# ============================================================================
from pyspark.sql import DataFrame
from pyspark.sql.functions import col
from requete import nodes, tests

@nodes.promote(tag="promote_revenue", pipeline="analytics", depends_on=["user_revenue"], env=["dev"])
def promote_dev(user_revenue_df: DataFrame) -> None:
    """Promotes validated revenue to dev promoted table."""
    user_revenue_df.write.mode("overwrite").saveAsTable("dev_user_revenue_promoted")

@nodes.promote(tag="promote_revenue", pipeline="analytics", depends_on=["user_revenue"], env=["prod"])
def promote_prod(user_revenue_df: DataFrame) -> None:
    """Promotes validated revenue to production promoted table."""
    user_revenue_df.write.mode("append").saveAsTable("prod.user_revenue_promoted")

@tests.promotion(tag="promote_revenue", env=["dev"])
def test_promote_dev(user_revenue_df: DataFrame):
    """Validates revenue before promotion in dev."""
    assert user_revenue_df.count() > 0, "Cannot promote empty dataset"

@tests.promotion(tag="promote_revenue", env=["prod"])
def test_promote_prod(user_revenue_df: DataFrame):
    """Validates revenue before promotion in production."""
    assert user_revenue_df.count() > 0, "Cannot promote empty dataset"

    # Business validation
    negative = user_revenue_df.filter(col("total_revenue") < 0).count()
    assert negative == 0, f"Found {negative} users with negative revenue"

    # Completeness check
    nulls = user_revenue_df.filter(col("total_revenue").isNull()).count()
    assert nulls == 0, f"Found {nulls} users with null revenue"
```

### Execution Flow

**Dev Environment:**

```
dev_session (spark)
    ↓
raw_users (mock) ──→ users_cleaned ──→ user_revenue ──→ write_revenue (dev table)
                           ↓                ↓
raw_orders (mock) ─────────┘                └──→ promote_revenue (if test passes)
                                                      ↓
                                              promotion_test validates
                                                      ↓
                                          dev_user_revenue_promoted
```

**Prod Environment:**

```
prod_session (spark)
    ↓
raw_users (table) ──→ users_cleaned ──→ user_revenue ──→ write_revenue (prod table)
                           ↓                ↓
raw_orders (table) ────────┘                └──→ promote_revenue (if test passes)
                                                      ↓
                                              promotion_test validates
                                                      ↓
                                          prod.user_revenue_promoted
```

---

## Best Practices

### 1. Use Explicit Schemas for Mock Data

```python
# ✅ GOOD: Explicit schema (cross-engine compatible)
schema = StructType([
    StructField("id", IntegerType(), True),
    StructField("value", DoubleType(), True)
])
df = sparkSession.createDataFrame([(1, 1.5)], schema)

# ❌ BAD: Implicit schema (may differ between engines)
df = sparkSession.createDataFrame([(1, 1.5)], ["id", "value"])
```

### 2. Keep Transforms Pure

```python
# ✅ GOOD: Pure function
@nodes.transform(tag="clean", pipeline="analytics", depends_on=["raw"])
def clean_data(raw_df: DataFrame) -> DataFrame:
    return raw_df.filter(col("status") == "active")

# ❌ BAD: Side effects
@nodes.transform(tag="clean", pipeline="analytics", depends_on=["raw"])
def clean_data(raw_df: DataFrame) -> DataFrame:
    external_api_call()  # ❌ Side effect!
    return raw_df.filter(col("status") == "active")
```

### 3. Use Descriptive Tags

```python
# ✅ GOOD
@nodes.transform(tag="users_with_revenue", pipeline="analytics", depends_on=["users", "orders"])

# ❌ BAD
@nodes.transform(tag="node_3", pipeline="analytics", depends_on=["node_1", "node_2"])
```

### 4. Write Comprehensive Tests

```python
# Test edge cases
@tests.unit(tag="calculate_discount")
def test_discount_edge_cases(sparkSession: SparkSession):
    # Test null handling
    # Test zero values
    # Test boundary conditions
    # Test empty DataFrames
    ...
```

### 5. Document with Docstrings

```python
@nodes.transform(tag="calculate_revenue", pipeline="analytics", depends_on=["orders"])
def calculate_revenue(orders_df: DataFrame) -> DataFrame:
    """
    Calculates total revenue with discounts applied.

    Business Rules:
    - Orders >= 10 items get 20% discount
    - Cancelled orders excluded
    - Refunded orders have negative revenue

    Args:
        orders: Raw order data with columns: order_id, quantity, price, status

    Returns:
        DataFrame with columns: order_id, revenue
    """
    ...
```

---

## Migration Guide

### From Existing PySpark Code

**Strategy 1: The "Strangler" (Minimal Refactor)**

Wrap existing code in a single transform node:

```python
# Before: monolithic_pipeline.py (2000 lines)
def run_pipeline(spark):
    # ... 2000 lines of logic ...
    pass

# After: Wrap in transform node
@nodes.transform(tag="legacy_pipeline", pipeline="my_pipeline", depends_on=["raw_data"])
def run_pipeline(raw_data_df: DataFrame) -> DataFrame:
    # ... same 2000 lines ...
    return final_result
```

Then gradually carve out smaller nodes as needed.

**Strategy 2: The "Architect" (Boundary Refactor)**

Split by team ownership / Business boundaries etc:

```python
# Platform team owns ingestion
@nodes.source(tag="raw_data", env=[...])

# Data science team owns transformations
@nodes.transform(tag="feature_engineering", depends_on=["raw_data"])

# Analytics team owns reporting
@nodes.transform(tag="reporting_metrics", depends_on=["feature_engineering"])
```

---

## Troubleshooting

### Common Errors

**Error: "Promotion test missing for tag 'X'"**

- **Cause:** `@nodes.promote()` without matching `@tests.promotion()`
- **Fix:** Add promotion test with same tag and env

**Error: "Circular dependency detected"**

- **Cause:** Node A depends on B, B depends on A
- **Fix:** Remove circular dependency, redesign DAG

**Error: "Tag 'X' not found in depends_on"**

- **Cause:** Referenced tag doesn't exist or wrong env
