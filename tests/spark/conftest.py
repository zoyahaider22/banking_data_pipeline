import pytest

from src.spark.load_data import (
    get_spark,
    load_accounts,
    load_branches,
    load_customers,
    load_transactions,
)
from src.spark.transformations import prepare_transactions


@pytest.fixture(scope="session")
def spark():
    session = get_spark("SparkTests")
    yield session
    session.stop()


@pytest.fixture(scope="session")
def transactions(spark):
    return prepare_transactions(load_transactions(spark))


@pytest.fixture(scope="session")
def accounts(spark):
    return load_accounts(spark)


@pytest.fixture(scope="session")
def customers(spark):
    return load_customers(spark)


@pytest.fixture(scope="session")
def branches(spark):
    return load_branches(spark)