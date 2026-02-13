# Requete Python Library

**Version:** 0.1.1

Requete is a Python library for defining data pipelines as code. It provides decorators that mark functions as pipeline nodes, enabling the Requete IDE to build DAGs, validate dependencies, and generate executable artifacts.

## Quick Start

### Installation

```bash
pip install requete
```

### Hello World Pipeline

```python
from pyspark.sql import DataFrame, SparkSession
from pyspark.sql.types import StructType, StructField, IntegerType
from requete import nodes, sessions, tests

# Create a session
@sessions.session(tag="dev_node", pipeline="hello_world", engine="spark", env=["dev"])
def dev_session() -> SparkSession:
    return SparkSession.builder.master("local[*]").getOrCreate()

# Read data
@nodes.source(tag="numbers", pipeline="hello_world", env=["dev"])
def load_numbers(sparkSession: SparkSession) -> DataFrame:
    schema = StructType([StructField("value", IntegerType(), True)])
    return sparkSession.createDataFrame([(1,), (2,), (3,)], schema)

# Transform data
@nodes.transform(tag="doubled", pipeline="hello_world", depends_on=["numbers"])
def double_values(numbers_df: DataFrame) -> DataFrame:
    return numbers_df.withColumn("value", numbers_df.value * 2)

# Test it
@tests.unit(tag="doubled")
def test_double(sparkSession: SparkSession):
    schema = StructType([StructField("value", IntegerType(), True)])
    input_df = sparkSession.createDataFrame([(5,)], schema)
    result = double_values(input_df)
    assert result.first()["value"] == 10

# Write results
@nodes.sink(tag="write", pipeline="hello_world", depends_on=["doubled"], env=["dev"])
def write_results(doubled_df: DataFrame) -> None:
    doubled_df.write.mode("overwrite").saveAsTable("doubled_numbers")
```

## Core Concepts

### Node Types

- **`@sessions.session`**: Create database connections
- **`@nodes.source`**: Read input data
- **`@nodes.backfill_source`**: Read historical data for backfills (receives `context` dict with CLI params)
- **`@nodes.transform`**: Transform DataFrames (pure functions)
- **`@nodes.sink`**: Write output data (always executes)
- **`@nodes.promote`**: Write output data conditionally (after tests pass)

### Test Types

- **`@tests.unit`**: Test logic with mock data
- **`@tests.integration`**: Test with real pipeline data
- **`@tests.promotion`**: Validate before promotion (required for promote nodes)
- **`@tests.source`**: Validate source node output data quality

### Environments

Define different implementations per environment:

```python
@nodes.source(tag="users", pipeline="my_pipeline", env=["dev"])
def users_dev(sparkSession: SparkSession) -> DataFrame:
    # Mock data for development
    return sparkSession.createDataFrame([...])

@nodes.source(tag="users", pipeline="my_pipeline", env=["prod"])
def users_prod(sparkSession: SparkSession) -> DataFrame:
    # Real data in production
    return sparkSession.table("prod.users")
```

## Key Features

- **Pure Functions**: Transforms are pure—same input always produces same output
- **Multi-Engine**: Write once in PySpark API, run on DuckDB/Spark/Snowflake
- **Environment Isolation**: Different implementations for dev/staging/prod
- **Type Safety**: Full type hints for LSP validation
- **Test-Driven**: First-class unit and integration testing
- **Zero Lock-in**: Generates standard Python artifacts

## Documentation

- **[Full Specification](SPECIFICATION.md)**: Complete reference for all decorators, rules, and examples
- **[FAQ](https://github.com/requete-dev/requete#faq)**: Common questions and design decisions

## Example Pipeline Structure

```
requete_pipelines/my_pipeline/
├── sessions/
│   ├── spark.py          # Spark session configurations
│   └── duckdb.py         # DuckDB session configurations
├── sources/
│   ├── users.py          # User data sources
│   └── orders.py         # Order data sources
├── transforms/
│   ├── clean_users.py    # Data cleaning
│   └── user_revenue.py   # Revenue calculations
├── sinks/
│   └── write_revenue.py  # Output writers
└── promotes/
    └── promote_revenue.py # Conditional promotion
```

## Philosophy

Requete treats data engineering as software engineering:

- **Local-First**: Develop on DuckDB locally, deploy to Spark/Snowflake in prod
- **Hot Reload**: Change code, press save, see results in 0.5 seconds
- **Compiler Model**: Generates deterministic artifacts that run anywhere
- **Best of Breed**: Bring your own IDE, AI, Git, scheduler—we don't lock you in

## Examples

### Multi-Engine Pipeline

```python
# duckdb.py - Fast local development
@sessions.session(tag="dev_node", pipeline="my_pipeline", engine="duckdb", env=["dev"])
def dev_session() -> SparkSession:
    from duckdb.experimental.spark.sql import SparkSession
    return SparkSession.builder.remote("local").getOrCreate()

# spark.py - Production cluster
@sessions.session(tag="prod_node", pipeline="my_pipeline", engine="spark", env=["prod"])
def prod_session() -> SparkSession:
    return SparkSession.builder.master("spark://cluster:7077").getOrCreate()

# All transforms work on both engines!
@nodes.transform(tag="calculate", pipeline="my_pipeline", depends_on=["data"])
def calculate(data_df: DataFrame) -> DataFrame:
    return data_df.groupBy("user_id").agg(sum("amount"))
```

### Conditional Promotion

```python
# Always write raw data
@nodes.sink(tag="write_raw", pipeline="my_pipeline", depends_on=["aggregated"], env=["prod"])
def write_raw(aggregated_df: DataFrame) -> None:
    aggregated_df.write.saveAsTable("raw_results")

# Only promote if tests pass
@nodes.promote(tag="promote", pipeline="my_pipeline", depends_on=["aggregated"], env=["prod"])
def promote_validated(aggregated_df: DataFrame) -> None:
    aggregated_df.write.saveAsTable("promoted_results")

# Gate with validation
@tests.promotion(tag="promote", env=["prod"])
def test_promotion(aggregated_df: DataFrame):
    assert aggregated_df.count() > 0
    assert aggregated_df.filter(col("revenue") < 0).count() == 0
```

### Backfill with Parameters

```python
from requete import nodes, sessions, tests

# Define backfill source that accepts parameters
@nodes.backfill_source(tag="orders", pipeline="analytics", env=["backfill"])
def orders_backfill(sparkSession: SparkSession, context: dict[str, str]) -> DataFrame:
    # Extract parameters from context dict
    from_date = context.get('from_date', '2024-01-01')
    to_date = context.get('to_date', '2024-12-31')
    table = context.get('table', 'orders')

    # Use parameters in query
    return sparkSession.table(table).filter(
        (col("date") >= from_date) & (col("date") < to_date)
    )

# Test source data quality
@tests.source(tag="orders", env=["backfill"])
def test_orders_backfill(orders_df: DataFrame):
    assert orders_df.count() > 0
    assert "date" in orders_df.columns
```

**Generate with CLI parameters:**

```bash
requete generate \
  --directory ./requete_pipelines \
  --pipeline analytics \
  --engine spark \
  --env backfill \
  --test-type integration \
  --backfill-source from_date=2024-01-01 \
  --backfill-source to_date=2024-01-31 \
  --backfill-source table=prod_orders
```

**Generated context:**

```python
# Backfill Context
context = {
    'from_date': '2024-01-01',
    'to_date': '2024-01-31',
    'table': 'prod_orders',
}

# Node receives context
df_cache['orders'] = orders_backfill(spark, context)
```

## Contributing

See [CONTRIBUTING.md](https://github.com/requete-dev/requete/blob/main/CONTRIBUTING.md) for development setup and guidelines.

## License

MIT License - see [LICENSE](https://github.com/requete-dev/requete/blob/main/LICENSE) for details.

## Support

- **GitHub Issues**: [github.com/requete-dev/requete/issues](https://github.com/requete-dev/requete/issues)
