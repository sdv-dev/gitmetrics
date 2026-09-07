"""Function to compute the metrics from the collected data."""

import pandas as pd

from gitmetrics.constants import METRIC_COLUMN_NAME, VALUE_COLUMN_NAME


def compute_metrics(issues, pull_requests, users, contributors, stargazers, stargazers_count=0):
    """Compute metrics for the given data.

    Args:
        issues (pd.DataFrame):
            Issues table.
        pull_requests (pd.DataFrame):
            Pull Requests table.
        users (pd.DataFrame):
            Unique Issues table.
        contributors (pd.DataFrame):
            Unique Contributors table.
        stargazers (pd.DataFrame):
            Unique Stargazers table.

    Returns:
        pd.DataFrame:
            Table with the compute metrics, in 3 columns containing the
            metric name, the computed value and a short description of
            the metric.
    """
    num_issues = len(issues)
    num_pull_requests = len(pull_requests)
    num_users = len(users)
    num_contributors = len(contributors)
    num_stargazers = len(stargazers) or stargazers_count
    non_contrib_users = users[~users.user.isin(contributors.user)]
    num_non_contrib_users = len(non_contrib_users)
    non_contrib_stars = stargazers[~stargazers.user.isin(contributors.user)]
    num_non_contrib_stars = len(non_contrib_stars)

    usr = num_users / num_stargazers if num_stargazers else None
    usrc = num_non_contrib_users / num_non_contrib_stars if num_non_contrib_stars else None

    return pd.DataFrame([
        {
            METRIC_COLUMN_NAME: 'num_issues',
            VALUE_COLUMN_NAME: num_issues,
            'description': 'Total number of Issues',
        },
        {
            METRIC_COLUMN_NAME: 'num_pull_requests',
            VALUE_COLUMN_NAME: num_pull_requests,
            'description': 'Total number of Pull Requests',
        },
        {
            METRIC_COLUMN_NAME: 'num_users',
            VALUE_COLUMN_NAME: num_users,
            'description': 'Total number of Issue Users',
        },
        {
            METRIC_COLUMN_NAME: 'num_contgributors',
            VALUE_COLUMN_NAME: num_contributors,
            'description': 'Total number of Contributors',
        },
        {
            METRIC_COLUMN_NAME: 'num_stargazers',
            VALUE_COLUMN_NAME: num_stargazers,
            'description': 'Total number of Stargazers',
        },
        {
            METRIC_COLUMN_NAME: 'num_non_contributor_users',
            VALUE_COLUMN_NAME: num_non_contrib_users,
            'description': 'Total number of Users that are not Contributors',
        },
        {
            METRIC_COLUMN_NAME: 'num_non_contributor_stargazers',
            VALUE_COLUMN_NAME: num_non_contrib_stars,
            'description': 'Total number of Stargazers that are not Contributors',
        },
        {
            METRIC_COLUMN_NAME: 'USR',
            VALUE_COLUMN_NAME: usr,
            'description': 'Users / Stargazers ratio',
        },
        {
            METRIC_COLUMN_NAME: 'USR-C',
            VALUE_COLUMN_NAME: usrc,
            'description': 'USR Excluding Contributors',
        },
    ])
