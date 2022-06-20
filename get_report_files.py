"""Sqlize Crystal Reports."""

import datetime
import ntpath as path
import os
import re
import time

import pyodbc
from dotenv import load_dotenv

load_dotenv()

CRYSTALDATABASE = os.environ.get(
    "CRYSTALDATABASE",
    "DRIVER={ODBC Driver 17 for SQL Server};SERVER=sqlServer;DATABASE=CrystalSQL;UID=joe;PWD=12345",
)
CRYSTALBOEOUTPUT = os.environ.get("CRYSTALBOEOUTPUT", "\\\\somewhere\\Output")

conn = pyodbc.connect(CRYSTALDATABASE, autocommit=True)
cursor = conn.cursor()


# next, load all the pdf links for recent runs

six_months_ago = time.time() - 15768000  # seconds in 6 months


def _walk(top):
    """Create modified implementation of os.walk() to only walk paths we need."""
    dirs = []
    nondirs = []

    # We may not have read permission for top, in which case we can't
    # get a list of the files the directory contains.  os.walk
    # always suppressed the exception then, rather than blow up for a
    # minor reason when (say) a thousand readable directories are still
    # left to visit.  That logic is copied here.
    try:
        # Note that scandir is global in this module due
        # to earlier import-*.
        scandir_it = os.scandir(top)
    except OSError as error:
        print(error)  # noqa: T201

        return

    with scandir_it:
        while True:
            try:
                try:
                    entry = next(scandir_it)
                except StopIteration:
                    break
            except OSError as error:
                print(error)  # noqa: T201

                return

            try:
                is_dir = entry.is_dir()

            except OSError:
                # If is_dir() raises an OSError, consider that the entry is not
                # a directory, same behaviour than os.path.isdir().
                is_dir = False

            if is_dir:
                # only dirs matching our pattern. remember re.match uses ^ start of string
                if re.match(r"\d|-", entry.name):  # modified in last 6 months
                    dirs.append(entry.name)
            else:
                if (
                    re.search(r".pdf$", entry.name, re.I)
                    and entry.stat().st_ctime > six_months_ago
                ):  # created in last 6 months
                    nondirs.append([entry.name, entry.stat().st_ctime])

    yield top, dirs, nondirs

    # Recurse into sub-directories
    islink, join = path.islink, path.join
    for dirname in dirs:

        new_path = join(top, dirname)
        # Issue #23605: os.path.islink() is used instead of caching
        # entry.is_symlink() result during the loop on os.scandir() because
        # the caller can replace the directory entry during the "yield"
        # above.
        if not islink(new_path):
            yield from _walk(new_path)


cursor.execute("DELETE FROM [CrystalSQL].[dbo].[Attachments] where 1=1;")
file_count = 0
for my_path in _walk(CRYSTALBOEOUTPUT):
    if len(my_path[2]):
        for this_file in my_path[2]:

            cursor.execute(
                "INSERT INTO [CrystalSQL].[dbo].[Attachments] (HRX,PDF,CreationDate, Name) VALUES (?, ?, ?, ?);",
                (
                    this_file[0].split("-")[0],
                    my_path[0] + "\\" + this_file[0],
                    datetime.datetime.fromtimestamp(this_file[1]),
                    this_file[0],
                ),
            )
            file_count += 1
            # print(file[0].split("-")[0], my_path[0] + "\\" + file[0], datetime.datetime.fromtimestamp(file[1]) ) # noqa: T201

print(f"Found {file_count} files.")  # noqa: T201

conn.close()
