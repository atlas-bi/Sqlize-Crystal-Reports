"""Sqlize Crystal Reports."""

import shutil
import subprocess
from pathlib import Path, PureWindowsPath

import pyodbc

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

cursor.execute("DELETE FROM [CrystalSQL].[dbo].[Query] where 1=1;")

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
                    "INSERT INTO [CrystalSQL].[dbo].[Query] (ReportName,Query,Title,Description)",
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

print(f"Loaded {query_count} from {count} reports.")

conn.close()
