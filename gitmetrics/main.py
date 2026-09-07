"""Main script."""

import datetime
import logging
import pathlib

import pandas as pd

from gitmetrics.constants import METRICS_SHEET_NAME
from gitmetrics.drive import get_or_create_gdrive_folder
from gitmetrics.github.repository import STARGAZERS_COLUMNS, RepositoryClient
from gitmetrics.github.repository_owner import RepositoryOwnerClient
from gitmetrics.github.traffic import TrafficClient
from gitmetrics.github.users import UsersClient
from gitmetrics.metrics import compute_metrics
from gitmetrics.output import create_spreadsheet, load_spreadsheet

LOGGER = logging.getLogger(__name__)

GDRIVE_LINK = 'gdrive://'

USER_COLUMNS = [
    'user',
    'name',
    'email',
    'blog',
    'company',
    'location',
    'twitter',
    'user_created_at',
    'user_updated_at',
    'bio',
]


def _get_repository_data(token, repository, previous=None, quiet=False):
    LOGGER.info('Getting information for repository %s', repository)
    repo_client = RepositoryClient(token, repository, quiet)
    if previous:
        prev_issues = previous['Issues']
        prev_issues = prev_issues[prev_issues.repository == repository]
        max_date = max(
            prev_issues['created_at'].max(),
            prev_issues['updated_at'].max(),
            prev_issues['closed_at'].max(),
        )
    else:
        prev_issues = None
        max_date = None

    issues = repo_client.get_issues(since=max_date)
    if issues.empty and prev_issues is not None:
        issues = prev_issues
    else:
        issues.insert(1, 'repository', repository)
        if prev_issues is not None and not prev_issues.empty:
            issues = pd.concat([issues, prev_issues], ignore_index=True)
            issues = issues.sort_values(['created_at', 'closed_at'])
            issues = issues.drop_duplicates(['repository', 'number'], keep='last')

    pull_requests = repo_client.get_pull_requests()
    pull_requests.insert(1, 'repository', repository)

    try:
        stargazers = repo_client.get_stargazers()
    except Exception:
        # Stargazer information is available only for repositories that we own
        # In order to continue with the flow without breaking we create an empty
        # dataframe with the expected columns.
        stargazers = pd.DataFrame(columns=STARGAZERS_COLUMNS)

    stargazers.insert(1, 'repository', repository)
    stargazers_count = repo_client.get_stargazer_count()

    return issues, pull_requests, stargazers, stargazers_count


def _get_repositories_list(token, owner, quiet=False):
    owner_client = RepositoryOwnerClient(token, owner, quiet)
    repositories = owner_client.get_repositories()
    return (owner + '/' + repositories)['repository'].tolist()


def _get_profiles(token, issues, pull_requests, stargazers, previous, quiet):
    all_users = pd.concat([issues['user'], pull_requests['user']], ignore_index=True)
    unique_users = all_users.dropna().unique().tolist()

    users = stargazers[USER_COLUMNS].drop_duplicates()

    if previous:
        users = pd.concat([users, previous['Unique Issue Users'][USER_COLUMNS]], ignore_index=True)
        users = pd.concat([users, previous['Unique Contributors'][USER_COLUMNS]], ignore_index=True)
        users = pd.concat([users, previous['Unique Stargazers'][USER_COLUMNS]], ignore_index=True)
        users = users.sort_values('user_updated_at').drop_duplicates('user', keep='last')

    known_users = users.user.dropna().unique()

    missing = list(set(unique_users) - set(known_users))
    if missing:
        LOGGER.info('Getting %s missing users', len(missing))
        users_client = UsersClient(token, quiet)
        missing_users = users_client.get_users(missing)
        users = pd.concat([users, missing_users], ignore_index=True)

    return users.sort_values('user').reset_index(drop=True)


def _get_issues(all_issues, profiles):
    issues = all_issues.drop_duplicates()
    issues = issues.merge(profiles, how='left', on='user', suffixes=('', '_DROP'))
    return issues.filter(regex='^(?!.*_DROP)').sort_values('created_at')


def _get_pull_requests(all_pull_requests, profiles):
    prs = all_pull_requests.merge(profiles, how='left', on='user').drop_duplicates()
    return prs.sort_values('created_at')


def _get_users(issues, profiles):
    issues_by_date = issues.sort_values('created_at')
    grouped = issues_by_date.groupby('user')
    users = grouped.created_at.first().to_frame()
    users['opened_issues'] = grouped.size()
    users['num_repositories'] = grouped.repository.nunique()
    users = users.reset_index()

    users = users.rename(columns={'created_at': 'first_issue_date'})
    users = users.merge(profiles, how='left', on='user')

    if not users.empty:
        days_between = (users['first_issue_date'] - users['user_created_at']).dt.days
    else:
        days_between = None

    users.insert(2, 'db_account_issue_creation', days_between)

    return users.sort_values('first_issue_date')


def _get_contributors(pull_requests):
    prs_by_date = pull_requests.sort_values('created_at')
    contributors = prs_by_date[USER_COLUMNS].drop_duplicates()
    contributors = contributors.sort_values('user').set_index('user')

    prs_by_user = pull_requests.groupby('user')
    contributors.insert(1, 'opened_prs', prs_by_user.size())
    contributors.insert(2, 'first_pr_date', prs_by_user.created_at.first())
    contributors.insert(3, 'num_repositories', prs_by_user.repository.nunique())

    return contributors.reset_index(drop=False).sort_values('first_pr_date')


def _get_stargazers(all_stargazers):
    stargazers = all_stargazers.sort_values('starred_at').drop_duplicates(subset='user')
    stargazers = stargazers.set_index('user')
    stargazers.insert(0, 'starred_repositories', all_stargazers.groupby('user').size())
    stargazers = stargazers.rename(columns={'repository': 'first_starred_repository'})
    return stargazers.reset_index().sort_values('starred_at')


def collect_project_metrics(
    token,
    repositories,
    output_path=None,
    quiet=False,
    incremental=True,
    add_metrics=False,
):
    """Pull data from GitHub to create metrics.

    Args:
        token (str):
            GitHub token to use.
        repositories (list[str]):
            List of repositories to analyze, passed as ``{org_name}/{repo_name}``
        output_path (str):
            Output path, including the ``xlsx`` extension, or name to use
            when creating the final filename
        quiet (bool):
            If True, disable the tqdm bars.
        incremental (bool):
            Whether to increment over the previous data (True) or start from
            scratch (False). Defatuls to True.
        add_metrics (bool):
            Whether to add the metrics tab. Defaults to False.

    Returns:
        dict[str, pd.DataFrame] or None:
            If output_path is None, a dict with the sheets is returned.
    """
    if not incremental:
        previous = None
    else:
        try:
            previous = load_spreadsheet(output_path, sheet_name=None)
        except FileNotFoundError:
            previous = None

    all_issues = pd.DataFrame()
    all_pull_requests = pd.DataFrame()
    all_stargazers = pd.DataFrame()

    all_repositories = []
    for repository in repositories:
        if '/' in repository:
            all_repositories.append(repository)
        else:
            all_repositories.extend(_get_repositories_list(token, repository, quiet))

    repo_stargazers_count = []
    for repository in all_repositories:
        try:
            issues, pull_requests, stargazers, stargazers_count = _get_repository_data(
                token=token, repository=repository, previous=previous, quiet=quiet
            )
            all_issues = pd.concat([all_issues, issues], ignore_index=True)
            all_pull_requests = pd.concat([all_pull_requests, pull_requests], ignore_index=True)
            all_stargazers = pd.concat([all_stargazers, stargazers], ignore_index=True)
            repo_stargazers_count.append(stargazers_count)

        except Exception:
            LOGGER.info(f'Failed to get repository data: {repository}.')

    profiles = _get_profiles(token, all_issues, all_pull_requests, all_stargazers, previous, quiet)

    issues = _get_issues(all_issues, profiles)
    pull_requests = _get_pull_requests(all_pull_requests, profiles)
    users = _get_users(all_issues, profiles)
    contributors = _get_contributors(pull_requests)
    stargazers = _get_stargazers(all_stargazers)

    sheets = {
        'Issues': issues,
        'Pull Requests': pull_requests,
        'Unique Issue Users': users,
        'Unique Contributors': contributors,
        'Unique Stargazers': stargazers,
    }
    if add_metrics:
        metrics = compute_metrics(
            issues,
            pull_requests,
            users,
            contributors,
            stargazers,
            stargazers_count=sum(repo_stargazers_count),
        )
        sheets = dict({METRICS_SHEET_NAME: metrics}, **sheets)

    if output_path:
        create_spreadsheet(output_path, sheets)
        return None

    return sheets


def collect_projects(
    token, projects, output_folder, quiet=False, incremental=True, add_metrics=False
):
    """Collect github metrics for multiple projects.

    Args:
        token (str):
            GitHub token to use.
        projects (dict[str, List[str]]):
            Projects to collect, passed as a dict of project names
            and lists of repositories.
        ouptut_folder (str):
            Folder in which the metrics will be stored.
        quiet (bool):
            If True, disable the tqdm bars.
        incremental (bool):
            Whether to increment over the previous data (True) or start from
            scratch (False). Defatuls to True.
        add_metrics (bool):
            Whether to add the metrics tab. Defaults to False.
    """
    if not projects:
        raise ValueError('No projects have been passed')

    for project, repositories in projects.items():
        if output_folder.startswith(GDRIVE_LINK):
            project_path = f'{output_folder}/{project}'
        else:
            project_path = str(pathlib.Path(output_folder) / project)

        collect_project_metrics(token, repositories, project_path, quiet, incremental, add_metrics)


def collect_traffic(token, projects, output_folder):
    """Collect github metrics for multiple projects.

    Args:
        token (str):
            GitHub token to use.
        projects (dict[str, List[str]]):
            Projects to collect, passed as a dict of project names
            and lists of repositories.
        ouptut_folder (str):
            Folder in which the metrics will be stored.
    """
    timestamp = datetime.datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
    for project, repositories in projects.items():
        for repository in repositories:
            repository_name = repository.split('/')[-1]
            if output_folder.startswith(GDRIVE_LINK):
                repo_folder = get_or_create_gdrive_folder(output_folder, repository_name)
                repo_path = f'{repo_folder}/{timestamp}'

            else:
                repo_path = str(pathlib.Path(output_folder) / project / repository_name)

            collect_project_traffic(token, repository, repo_path)


def collect_project_traffic(token, repository, repo_path):
    """Collects traffic data (popular referrers & paths) from GitHub repositories.

    Args:
        token (str):
            GitHub token for authentication.

        repository (str):
            Repository name such as "owner/repository".

        repo_path (str):
            Output path to store the results.

    Returns:
        dict[str, pd.DataFrame] or None:
            If repo_path is None, returns a dictionary containing traffic data.
    """
    client = TrafficClient(token)
    try:
        traffic_data = client.get_all_traffic(repository)

    except Exception as e:
        LOGGER.warning(f'Failed to fetch traffic data for {repository}: {e}')

    if repo_path:
        create_spreadsheet(f'{GDRIVE_LINK}{repo_path}', traffic_data)
        return None

    return traffic_data
