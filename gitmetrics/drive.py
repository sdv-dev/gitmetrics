"""Functions to upload to and download from google drive."""

import json
import logging
import os
import pathlib
import tempfile

import yaml
from pydrive.auth import GoogleAuth
from pydrive.drive import GoogleDrive

XLSX_MIMETYPE = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
SPREADSHEET_MIMETYPE = 'application/vnd.google-apps.spreadsheet'
PYDRIVE_CREDENTIALS = 'PYDRIVE_CREDENTIALS'

LOGGER = logging.getLogger(__name__)
GDRIVE_LINK = 'gdrive://'
MAX_UPLOAD_RETRIES = 10


def is_drive_path(path):
    """Tell if the drive is a Google Drive path or not."""
    return path.startswith(GDRIVE_LINK)


def split_drive_path(path):
    """Extract the folder and filename from the google drive path string."""
    assert is_drive_path(path), f'{path} is not a google drive path'
    folder, filename = path[9:].split('/')
    return folder, filename


def _get_drive_client():
    tmp_credentials = os.getenv(PYDRIVE_CREDENTIALS)
    if not tmp_credentials:
        gauth = GoogleAuth()
        gauth.LocalWebserverAuth()
    else:
        with tempfile.TemporaryDirectory() as tempdir:
            credentials_file_path = pathlib.Path(tempdir) / 'credentials.json'
            credentials_file_path.write_text(tmp_credentials)

            credentials = json.loads(tmp_credentials)

            settings = {
                'client_config_backend': 'settings',
                'client_config': {
                    'client_id': credentials['client_id'],
                    'client_secret': credentials['client_secret'],
                },
                'save_credentials': True,
                'save_credentials_backend': 'file',
                'save_credentials_file': str(credentials_file_path),
                'get_refresh_token': True,
            }
            settings_file = pathlib.Path(tempdir) / 'settings.yaml'
            settings_file.write_text(yaml.safe_dump(settings))

            gauth = GoogleAuth(str(settings_file))
            gauth.LocalWebserverAuth()

    return GoogleDrive(gauth)


def _find_file(drive, filename, folder):
    query = {'q': f"'{folder}' in parents and trashed=false"}
    files = drive.ListFile(query).GetList()
    for found_file in files:
        if filename == found_file['title']:
            return found_file

    raise FileNotFoundError(f"File '{filename}' not found in Google Drive folder {folder}")


def upload_spreadsheet(content, filename, folder):
    """Upload spredsheet to google drive.

    Args:
        content (BytesIO):
            Content of the spredsheet, passed as a BytesIO object.
        filename (str):
            Name of the spreadsheet to create.
        folder (str):
            Id of the Google Drive Folder where the spreadshee must be created.
    """
    drive = _get_drive_client()

    try:
        drive_file = _find_file(drive, filename, folder)
    except FileNotFoundError:
        file_config = {'title': filename, 'parents': [{'id': folder}]}
        drive_file = drive.CreateFile(file_config)

    content.seek(0)
    drive_file.content = content

    retries = 0
    while retries != MAX_UPLOAD_RETRIES:
        try:
            if drive_file.get('mimeType') == SPREADSHEET_MIMETYPE:
                drive_file.Upload()
            else:
                drive_file.Upload({'convert': True})

            LOGGER.info('Created file %s', drive_file.metadata['alternateLink'])
            break
        except Exception as e:
            retries += 1
            LOGGER.warning(
                'Upload failed (%s/%s) for %s: %s',
                retries,
                MAX_UPLOAD_RETRIES,
                drive_file.get('title', 'unknown'),
                str(e),
            )
            if retries == MAX_UPLOAD_RETRIES:
                raise


def download_spreadsheet(folder, filename):
    """Download a spredsheet from google drive.

    Args:
        folder (str):
            Id of the Google Drive Folder where the spreadshee must be created.
        filename (str):
            Name of the spreadsheet to create.

    Returns:
        BytesIO:
            BytesIO object with the contents of the spreadsheet.
            If the file is not found, returns None

    Raises:
        FileNotFoundError:
            If the file does not exist in the indicated folder.
    """
    drive = _get_drive_client()

    drive_file = _find_file(drive, filename, folder)
    drive_file.FetchContent(mimetype=XLSX_MIMETYPE)
    return drive_file.content


def get_or_create_gdrive_folder(parent_folder: str, folder_name: str) -> str:
    """Check if a folder exists in Google Drive, create it if not, and return its ID.

    Args:
        parent_folder (str):
            ID of the parent Google Drive folder.
        folder_name (str):
            Name of the folder to check or create.

    Returns:
        str:
            The Google Drive folder ID.
    """
    drive = _get_drive_client()

    # Check if folder already exists
    if parent_folder.startswith(GDRIVE_LINK):
        parent_folder = parent_folder.replace(GDRIVE_LINK, '')

    query = {
        'q': f"title = '{folder_name}' and mimeType = 'application/vnd.google-apps.folder' "
        f"and '{parent_folder}' in parents and trashed = false"
    }
    folders = drive.ListFile(query).GetList()

    if folders:
        return folders[0]['id']  # Return existing folder ID

    # Create folder if it does not exist
    folder_metadata = {
        'title': folder_name,
        'mimeType': 'application/vnd.google-apps.folder',
        'parents': [{'id': parent_folder}],
    }
    folder = drive.CreateFile(folder_metadata)
    folder.Upload()

    return folder['id']
