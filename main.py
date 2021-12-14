"""Sqlize Crystal Reports."""

import datetime
import ntpath as path
import os
import re
import shutil
import subprocess
import time
from pathlib import Path, PureWindowsPath

import pyodbc
import requests
import urllib3
import xmltodict

import settings
from crystal_parser import Report

rpt_fldr = Path(__file__).parent / "crystal_rpt"
xml_fldr = Path(__file__).parent / "crystal_xml"

# remove report folder
shutil.rmtree(rpt_fldr, ignore_errors=True)
rpt_fldr.mkdir(exist_ok=True)

# copy in reports
for report in Path(settings.rpt_src).glob("*.rpt"):
    shutil.copyfile(settings.rpt_src + report.name, str(rpt_fldr / report.name))

# remove xml folder
shutil.rmtree(xml_fldr, ignore_errors=True)
Path(xml_fldr).mkdir(exist_ok=True)

print("Downloaded ", len(list(rpt_fldr.rglob(f"*"))), "files.")

# convert all reports to xml
for report in rpt_fldr.glob("*.rpt"):
    # if there are a ton of reports using threading might speed things up!
    try:
        command = subprocess.run(
            [
                str((Path(__file__).parent / "RptToXml" / "RptToXml.exe").absolute()),
                str((rpt_fldr / report.name).absolute()),
                str((xml_fldr / (report.stem + ".xml")).absolute()),
            ],
            capture_output=True,
        )
        if command.stderr:
            print(report.name, str(command.stderr))

    except Exception as e:
        print(report.name, str(e))
        continue

print("Converted ", len(list(xml_fldr.rglob(f"*"))), "files.")

conn = pyodbc.connect(settings.database, autocommit=True)
cursor = conn.cursor()

cursor.execute("DELETE FROM [CrystalSQL].[dbo].[Templates] where 1=1;")

count = 0
query_count = 0
for xml in xml_fldr.glob("*.xml"):

    try:
        report = Report(str((xml_fldr / xml.name).absolute()))
        title = report.title()
        description = report.description()

        for sql in report.sql():
            cursor.execute(
                "%s %s"
                % (
                    "INSERT INTO [CrystalSQL].[dbo].[Templates] (ReportName,Query,Title,Description)",
                    " VALUES (?,?,?,?)",
                ),
                xml.stem + ".rpt",
                sql,
                title,
                description,
            )
            query_count = query_count + 1
        count = count + 1

    except Exception as e:
        print(xml.name, str(e))

print(f"Loaded {query_count} queries from {count} reports.")


# get report id's from boe server. The report id's can be later used to generate
# run links for the reports.
# for more details see the sap docs: https://help.sap.com/viewer/0ef63ba725cd41a8ab4a69c226ec6b07/4.3.1/en-US/ec572a3c6fdb101497906a7cb0e91070.html
# remember, this is an xml string. if you have special chars in your password, encode them!
# for example, < encodes as &lt;
if settings.fetch_report_data == True:

    r = requests.post(
        f"{settings.sap_api_url}:6405/biprws/logon/long",
        json={
            "userName": settings.sap_api_username,
            "password": settings.sap_api_password,
            "auth": "secEnterprise",
        },
        headers={"Content-Type": "application/json"},
    )
    # verify successful login
    if "logonToken" not in r.text:
        raise ValueError(f"Failed to login:\n{r.text}")

    headers = {"X-SAP-LogonToken": r.headers["X-SAP-LogonToken"]}

    # get documents. the API only returns 50 documents in a list
    # so we should while loop until results are < 50.
    iteration = 0
    batch_size = 50
    size = batch_size

    cursor.execute("DELETE FROM [CrystalSQL].[dbo].[Documents] where 1=1;")

    while size == batch_size:
        offset = iteration * batch_size

        # get batch of reports
        batch = requests.get(
            f"{settings.sap_api_url}:6405/biprws/raylight/v1/documents?offset={offset}&limit={batch_size}",
            headers=headers,
        )

        docs = xmltodict.parse(batch.text)["documents"]["document"]

        size = len(docs)

        for doc in docs:
            cursor.execute(
                "INSERT INTO [CrystalSQL].[dbo].[Documents] (Name,Description,FolderId,Cuid,DocumentId) VALUES (?, ?, ?, ?, ?);",
                (
                    doc.get("name"),
                    doc.get("description"),
                    doc.get("folderId"),
                    doc.get("cuid"),
                    doc.get("id"),
                ),
            )
        iteration += 1

    doc_count = ((iteration - 1) * batch_size) + size
    print(f"Found {doc_count} documents.")

    # then get reports for all the documents
    cursor.execute("DELETE FROM [CrystalSQL].[dbo].[Reports] where 1=1;")

    # get the docs ids
    doc_ids = cursor.execute(
        "select documentid from [CrystalSQL].[dbo].[Documents]"
    ).fetchall()

    report_count = 0
    for doc in doc_ids:
        doc_id = doc[0]

        # get batch of reports
        batch = requests.get(
            f"{settings.sap_api_url}:6405/biprws/raylight/v1/documents/{doc_id}/reports",
            headers=headers,
        )

        batch_dict = xmltodict.parse(batch.text)
        if "error" in batch_dict:
            print(batch_dict)
            continue

        reports = batch_dict["reports"]["report"]

        # xmltodict will explode when single matches are there, so check for that.
        if "name" in reports:
            cursor.execute(
                "INSERT INTO [CrystalSQL].[dbo].[Reports] (Name,Reference,ReportId,DocumentId) VALUES (?, ?, ?, ?);",
                (
                    reports.get("name"),
                    reports.get("reference"),
                    reports.get("id"),
                    doc_id,
                ),
            )
            report_count += 1
        else:

            for report in reports:
                cursor.execute(
                    "INSERT INTO [CrystalSQL].[dbo].[Reports] (Name,Reference,ReportId,DocumentId) VALUES (?, ?, ?, ?);",
                    (
                        report.get("name"),
                        report.get("reference"),
                        report.get("id"),
                        doc_id,
                    ),
                )

                report_count += 1

    print(f"Found {report_count} reports.")

    # objects

    iteration = 0
    batch_size = 50
    size = batch_size

    cursor.execute("DELETE FROM [CrystalSQL].[dbo].[Objects] where 1=1;")

    while size == batch_size:

        # get batch of reports
        batch = requests.get(
            f"{settings.sap_api_url}:6405/biprws/bionbi/content/list?page={iteration}&pageSize={batch_size}",
            headers=headers,
        )

        docs = xmltodict.parse(batch.text)["feed"]["entry"]

        size = len(docs)

        for doc in docs:
            doc = doc["content"]["attrs"]
            # print(doc)
            cursor.execute(
                "INSERT INTO [CrystalSQL].[dbo].[Objects] (Title,Cuid,StatusType,Type, LastRun) VALUES (?, ?, ?, ?, ?);",
                (
                    doc["attr"][3].get("#text"),
                    doc["attr"][0].get("#text"),
                    doc["attr"][1].get("#text"),
                    doc["attr"][4].get("#text"),
                    doc["attr"][2].get("#text"),
                ),
            )
        iteration += 1

    doc_count = ((iteration - 1) * batch_size) + size
    print(f"Found {doc_count} objects.")

    # logoff or you'll run out of sessions lol
    try:
        requests.post(f"{settings.sap_api_url}:6405/biprws/logoff", headers=headers)
    except BaseException as e:
        print(str(e))


# next, load all the pdf links for recent runs

six_months_ago = time.time() - 15768000  # seconds in 6 months


def _walk(top):
    """Modified implementation of os.walk() to only walk paths we need."""
    dirs = []
    nondirs = []
    walk_dirs = []

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
        print(error)

        return

    with scandir_it:
        while True:
            try:
                try:
                    entry = next(scandir_it)
                except StopIteration:
                    break
            except OSError as error:
                print(error)

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


if settings.fetch_report_files is True:
    cursor.execute("DELETE FROM [CrystalSQL].[dbo].[Attachments] where 1=1;")
    file_count = 0
    for my_path in _walk(settings.crystal_boe_output_drive):
        if len(my_path[2]):
            for file in my_path[2]:

                cursor.execute(
                    "INSERT INTO [CrystalSQL].[dbo].[Attachments] (HRX,PDF,CreationDate, Name) VALUES (?, ?, ?, ?);",
                    (
                        file[0].split("-")[0],
                        my_path[0] + "\\" + file[0],
                        datetime.datetime.fromtimestamp(file[1]),
                        file[0],
                    ),
                )
                file_count += 1
                # print(file[0].split("-")[0], my_path[0] + "\\" + file[0], datetime.datetime.fromtimestamp(file[1]) )

    print(f"Found {file_count} files.")


conn.close()
