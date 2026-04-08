"""GitMetrics CLI."""

import argparse
import logging
import os
import pathlib
import sys
import warnings

import yaml

from gitmetrics.consolidate import consolidate_metrics
from gitmetrics.main import collect_projects, collect_traffic
from gitmetrics.summarize import summarize_metrics

LOGGER = logging.getLogger(__name__)


def _env_setup(logfile, verbosity):
    warnings.simplefilter('ignore')

    format_ = '%(asctime)s - %(levelname)s - %(message)s'
    level = (3 - verbosity) * 10
    logging.basicConfig(filename=logfile, level=level, format=format_)
    logging.getLogger('gitmetrics').setLevel(level)
    logging.getLogger().setLevel(logging.WARN)


def _load_config(config_path):
    config_path = pathlib.Path(config_path)
    config = yaml.safe_load(config_path.read_text())

    import_config = config.pop('import_config', None)
    if import_config:
        import_config_path = pathlib.Path(import_config)
        if import_config_path.is_absolute():
            import_config_path = config_path.parent / import_config_path

        import_config = _load_config(import_config_path)
        import_projects = import_config['projects']

        import_config.update(config)
        config = import_config

        config_projects = config['projects']
        for project, repositories in config_projects.items():
            if not repositories:
                config_projects[project] = import_projects[project]

    return config


def _collect(args, parser):
    token = args.token or os.getenv('GITHUB_TOKEN')
    if token is None:
        token = input('Please input your GitHub Token: ')

    config = _load_config(args.config_file)
    config_projects = config['projects']

    projects = {}
    if args.repositories:
        if not args.projects:
            parser.error('If repositories are given, project name must be provided.')
        elif len(args.projects) > 1:
            parser.error('If repositories are given, only one project name must be provided.')

        projects = {args.projects[0]: args.repositories}

    elif not args.projects:
        projects = config_projects

    else:
        for project in args.projects:
            if project not in config_projects:
                LOGGER.error('Unknown project %s', project)
                return

            projects[project] = config_projects[project]

    collect_projects(
        token=token,
        projects=projects,
        output_folder=args.output_folder,
        quiet=args.quiet,
        incremental=args.incremental,
        add_metrics=args.add_metrics,
    )


def _traffic_collection(args, parser):
    token = args.token or os.getenv('GITHUB_TOKEN')
    if token is None:
        token = input('Please input your GitHub Token: ')

    config = _load_config(args.config_file)
    config_projects = config['projects']

    projects = {}
    if args.repositories:
        if not args.projects:
            parser.error('If repositories are given, project name must be provided.')
        elif len(args.projects) > 1:
            parser.error('If repositories are given, only one project name must be provided.')

        projects = {args.projects[0]: args.repositories}

    elif not args.projects:
        projects = config_projects

    else:
        for project in args.projects:
            if project not in config_projects:
                LOGGER.error('Unknown project %s', project)
                return

            projects[project] = config_projects[project]

    collect_traffic(
        token=token,
        projects=projects,
        output_folder=args.output_folder,
    )


def _summarize(args, parser):
    config = _load_config(args.config_file)
    projects = config['projects']
    vendors = config['vendors']

    summarize_metrics(
        projects=projects,
        vendors=vendors,
        input_folder=args.input_folder,
        dry_run=args.dry_run,
        verbose=args.verbose,
    )


def _consolidate(args, parser):
    config = _load_config(args.config_file)
    projects = config['projects']

    consolidate_metrics(
        projects=projects,
        output_folder=args.output_folder,
        dry_run=args.dry_run,
        verbose=args.verbose,
    )


def _get_parser():
    # Logging
    logging_args = argparse.ArgumentParser(add_help=False)
    logging_args.add_argument(
        '-v',
        '--verbose',
        action='count',
        default=0,
        help='Be verbose. Use `-vv` for increased verbosity.',
    )
    logging_args.add_argument(
        '-l', '--logfile', help='If given, file where the logs will be written.'
    )

    parser = argparse.ArgumentParser(
        prog='gitmetrics',
        description='GitMetrics Command Line Interface',
        parents=[logging_args],
    )
    parser.set_defaults(action=None)
    action = parser.add_subparsers(title='action')
    action.required = True

    # Collect
    collect = action.add_parser('collect', help='Collect github metrics.', parents=[logging_args])
    collect.set_defaults(action=_collect)

    collect.add_argument(
        '-o',
        '--output-folder',
        type=str,
        required=True,
        help='Output folder path.',
    )
    collect.add_argument('-t', '--token', type=str, required=False, help='GitHub Token to use.')
    collect.add_argument(
        '-p',
        '--projects',
        type=str,
        nargs='*',
        help='Projects to collect. Defaults to ALL if not given',
    )
    collect.add_argument(
        '-c',
        '--config-file',
        type=str,
        default='config.yaml',
        help='Path to the configuration file.',
    )
    collect.add_argument(
        '-q', '--quiet', action='store_true', help='Do not user tqdm progress bars.'
    )
    collect.add_argument(
        '-m', '--add-metrics', action='store_true', help='Whether to add a metrics tab.'
    )
    collect.add_argument('-r', '--repositories', nargs='*', help='List of repositories to add.')
    collect.add_argument(
        '-n',
        '--not-incremental',
        dest='incremental',
        action='store_false',
        help='Start from scratch instead of incrementing over existing data.',
    )
    # Consolidate
    consolidate = action.add_parser(
        'consolidate', help='Consolidate github metrics', parents=[logging_args]
    )
    consolidate.set_defaults(action=_consolidate)
    consolidate.add_argument(
        '-c',
        '--config-file',
        type=str,
        default='config.yaml',
        help='Path to the configuration file.',
    )
    consolidate.add_argument(
        '-d',
        '--dry-run',
        action='store_true',
        help='Do not actually create the conslidated overview file. Just calculate it.',
    )
    consolidate.add_argument(
        '-o',
        '--output-folder',
        type=str,
        required=True,
        help='Output folder path.',
    )

    # Traffic
    traffic = action.add_parser(
        'traffic', help='Collect github traffic metrics.', parents=[logging_args]
    )
    traffic.set_defaults(action=_traffic_collection)

    traffic.add_argument('-t', '--token', type=str, required=False, help='GitHub Token to use.')
    traffic.add_argument(
        '-c',
        '--config-file',
        type=str,
        default='traffic_config.yaml',
        help='Path to the configuration file.',
    )
    traffic.add_argument(
        '-o', '--output-folder', type=str, required=True, help='Output folder path.'
    )
    traffic.add_argument(
        '-p',
        '--projects',
        type=str,
        nargs='*',
        help='Projects to collect. Defaults to ALL if not given',
    )
    traffic.add_argument('-r', '--repositories', nargs='*', help='List of repositories to add.')

    # Summarize
    summarize = action.add_parser(
        'summarize', help='Summarize the GitMetrics information.', parents=[logging_args]
    )
    summarize.set_defaults(action=_summarize)
    summarize.add_argument(
        '-c',
        '--config-file',
        type=str,
        default='summarize_config.yaml',
        help='Path to the configuration file.',
    )
    summarize.add_argument(
        '-i',
        '--input-folder',
        type=str,
        required=True,
        help='Path to the folder containing xlsx files, with the calculated GitHub metrics.',
    )
    summarize.add_argument(
        '-d',
        '--dry-run',
        action='store_true',
        help='Do not actually create the summary results file. Just calculate them.',
    )
    return parser


def main():
    """Run the GitMetrics CLI."""
    parser = _get_parser()
    if len(sys.argv) < 2:
        parser.print_help()
        sys.exit(0)

    args = parser.parse_args()

    _env_setup(args.logfile, args.verbose)
    args.action(args, parser)


if __name__ == '__main__':
    main()
