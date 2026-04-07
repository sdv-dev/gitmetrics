<div align="center">
<br/>
<p align="center">
    <i>An open source project by Engineering at <a href="https://datacebo.com">DataCebo</a>.</i>
</p>

[![Dev Status](https://img.shields.io/badge/Dev%20Status-5%20--%20Production%2fStable-green)](https://pypi.org/search/?c=Development+Status+%3A%3A+5+-+Production%2FStable)
[![Slack](https://img.shields.io/badge/Slack-Join%20now!-36C5F0?logo=slack)](https://bit.ly/sdv-slack-invite)

<div align="center">
  <a href="https://datacebo.com">
    <picture>
      <img align="center" width=40% src="https://github.com/sdv-dev/GitMetrics/blob/main/docs/images/datacebo-logo.png"></img>
    </picture>
  </a>
</div>

</div>

<br/>

<div align="left">
  <picture>
    <img align="center" width=25% src="https://github.com/sdv-dev/GitMetrics/blob/main/docs/images/gitmetrics-logo.png"></img>
  </picture>
</div>

---


**GitMetrics** extracts metrics from GitHub Projects, generating spreadsheets with repository analytics.

## Output

The result is a spreadsheet that will contain 5 tabs (for each given project):

- **Issues**:
    Where all the issues are listed, including data about
    the users who created them.
- **Pull Requests**:
    Where all the pull requests are listed, including data about
    the users who created them.
- **Unique Issue Users**:
    Where the unique users that created issues
    are listed with all the information existing in their profile
- **Unique Contributors**:
    Where the unique users that created pull requests
    are listed with all the information existing in their profile
- **Unique Stargazers**:
    Where the unique users that stargazed the repositories
    are listed with all the information existing in their profile

Optionally, an additional spreadsheet called **Metrics** will be created with the
aggregation metrics for the entire project.


# Install
Install gitmetrics using pip:
```shell
pip install git+ssh://git@github.com/datacebo/gitmetrics
```

## Local Usage
Collect metrics from GitHub by running `gitmetrics` on your computer. You need to provide the following:

1. A GitHub Token. Documentation about how to create a Personal Access Token can be found
   [here](https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/creating-a-personal-access-token)
2. A list of GitHub Repositories for which to collect the metrics, defined in a YAML file. The repositories need to be given as `{org-name}/{repo-name}`, (e.g. `sdv-dev/SDV`). See [daily_summarization_config.yaml](./daily_summarization_config.yaml) for an example.
3. (__Optional__) A filename where the output will be stored. If a name containing the `.xlsx`
   extension is given (like `path/to/my-filename.xlsx`), it will be used as provided.
   Otherwise, a filename will be created as `github-metrics-{name}-{today}.xlsx` within
   the same folder where the script is run.
    - For example, if `sdv` is passed as the name,
    and the script is run on November, 9th, 2021, the output file will be
    `github-metrics-sdv-2021-11-09.xlsx`.

You can run gitmetrics with the following CLI command:

```shell
gitmetrics collect --token {GITHUB_TOKEN} --add-metrics --config-file daily_summarization_config.yaml
```

## Google Drive Integration

GitMetrics is capable of reading and writing results in Google Spreadsheets. The following is required:

1. The `output_path` needs to be given as a Google Drive path with the following format:
   `gdrive://<folder-id>/<filename>`.

2. A set of Google Drive Credentials need to be provided in the format required by `PyDrive`. The
   credentials can be stored in a `credentials.json` file within the working directory, alongside
   the corresponding `settings.yaml` file, or passed via the `PYDRIVE_CREDENTIALS` environment
   variable.
   - See [instructions from PyDrive](https://pythonhosted.org/PyDrive/quickstart.html).

## Workflows
1. **Weekly Collection**: On a weekly basis, this workflow collects GitHub metrics for the repositories defined in [weekly_extraction_config.yaml](./weekly_extraction_config.yaml).
2. **Daily Collection**: On a daily basis, this workflow collects GitHub metrics for the repositories defined in [daily_summarization_config.yaml](./daily_summarization_config.yaml).
3. **Daily Summarize**: On a daily basis, this workflow summarizes the GitHub metrics (from the daily collection). The summarized data is published to a GitHub repo: [gitmetrics_growth_summary.xlsx](https://github.com/sdv-dev/sdv-dev.github.io/blob/gatsby-home/assets/gitmetrics_growth_summary.xlsx)
