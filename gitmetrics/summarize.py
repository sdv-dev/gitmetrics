"""Summarize GitMetrics."""

import logging
import os

import pandas as pd

from gitmetrics.constants import ECOSYSTEM_COLUMN_NAME
from gitmetrics.output import create_spreadsheet, load_spreadsheet
from gitmetrics.time_utils import get_current_year, get_dt_now_spelled_out, get_min_max_dt_in_year

dir_path = os.path.dirname(os.path.realpath(__file__))


LOGGER = logging.getLogger(__name__)

TOTAL_COLUMN_NAME = 'Total Since Beginning'
OUTPUT_FILENAME = 'GitHub_Summary'
SHEET_NAMES = ['Unique users', 'User issues', 'vendor-mapping', 'metainfo']
START_YEAR = 2021


def _extract_row(df, date_column):
    row = {TOTAL_COLUMN_NAME: [len(df)]}
    for year in range(START_YEAR, get_current_year() + 1):
        min_datetime, max_datetime = get_min_max_dt_in_year(year)
        matching_df = df[df[date_column] >= min_datetime]
        matching_df = matching_df[matching_df[date_column] <= max_datetime]
        row[year] = [len(matching_df)]
    return row


def summarize_metrics(
    projects,
    vendors,
    input_folder,
    dry_run=False,
    verbose=False,
):
    """Summarize GitMetrics.

    Args:
        projects (dict[str, str | list[str]]):
            List of projects/ecosysems to summarize. Must contain
                - ecosystem (str): The user facing name of the ecossytem.
                - github_org (str): The GitHub organization for this ecosystem.

        vendors (dict[str, str | list[str]]):
            The vendors and the projects owned by the mentioned vendor.
            For each vendor, the following must be defined:
                - name (str): The actual name of the vendor.
                - github_org (str): The GitHub organization for this vendor.

        input_folder (str):
            The folder containing the location of the collected GitHub metrics.
            The folder must only contain spreadsheet (xlsx) files.
            The name of each file must match the `github_org` (lowercase) in
                summarize_project_definitions.yaml.
            The GitHub metrics are computed from the xlsx files in this folder.

        dry_run (bool):
            Whether of not to actually upload the summary results.
            If True, it just calculate the summary results. Defaults to False.

        verbose (bool):
            If True, will output the dataframes of the summary metrics
            (one dataframe for each sheet). Defaults to False.

    """
    vendor_df = pd.DataFrame.from_records(vendors)
    unique_users_df = _create_df()
    users_issues_df = _create_df()

    projects.extend(vendors)
    for project_info in projects:
        ecosystem_name = project_info['ecosystem']

        github_org = project_info.get('github_org', ecosystem_name)
        if not github_org:
            users_issues_df = append_row(users_issues_df, {ECOSYSTEM_COLUMN_NAME: [ecosystem_name]})
            unique_users_df = append_row(unique_users_df, {ECOSYSTEM_COLUMN_NAME: [ecosystem_name]})
            continue
        github_org = github_org.lower()

        filename = f'{github_org}'
        metrics_filepath = os.path.join(input_folder, filename)
        df = load_spreadsheet(metrics_filepath, sheet_name=None)

        unique_issue_users_df = df['Unique Issue Users']
        unique_users_row = _extract_row(
            unique_issue_users_df,
            'first_issue_date',
        )
        unique_users_row[ECOSYSTEM_COLUMN_NAME] = [ecosystem_name]
        unique_users_df = append_row(unique_users_df, unique_users_row)

        issues_df = df['Issues']
        issues_row = _extract_row(
            issues_df,
            'created_at',
        )
        issues_row[ECOSYSTEM_COLUMN_NAME] = [ecosystem_name]
        users_issues_df = append_row(users_issues_df, issues_row)

    vendor_df = vendor_df.rename(columns={vendor_df.columns[0]: ECOSYSTEM_COLUMN_NAME})
    runtime_data = {
        'index': ['date'],
        'value': [get_dt_now_spelled_out()],
    }
    metainfo_df = pd.DataFrame(runtime_data)
    sheets = {
        SHEET_NAMES[0]: unique_users_df,
        SHEET_NAMES[1]: users_issues_df,
        SHEET_NAMES[2]: vendor_df,
        SHEET_NAMES[3]: metainfo_df,
    }
    if verbose:
        for sheet_name, df in sheets.items():
            LOGGER.info(f'Sheet Name: {sheet_name}')
            LOGGER.info(df.to_string())
    if not dry_run:
        # Write to local directory
        output_path = os.path.join(dir_path, OUTPUT_FILENAME)
        create_spreadsheet(output_path=output_path, sheets=sheets)


def _create_df():
    columns = [ECOSYSTEM_COLUMN_NAME, TOTAL_COLUMN_NAME]
    for year in range(START_YEAR, get_current_year() + 1):
        columns.append(year)
    return pd.DataFrame(columns=columns)


def append_row(df, row):
    """Append a dictionary as a row to a DataFrame."""
    return pd.concat([df, pd.DataFrame(data=row)], ignore_index=True)
