"""Sqlize Crystal Reports."""

import os
import shutil
import subprocess
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

import pyodbc
from dotenv import load_dotenv

from scripts.crystal_parser import Report

load_dotenv()

RTPSRC = os.environ.get("RPTSRC", "\\\\Drive\\Input")
CRYSTALDATABASE = os.environ.get(
    "CRYSTALDATABASE",
    "DRIVER={ODBC Driver 17 for SQL Server};SERVER=sqlServer;DATABASE=CrystalSQL;UID=joe;PWD=12345",
)

rpt_fldr = Path(__file__).parent / "crystal_rpt"
xml_fldr = Path(__file__).parent / "crystal_xml"


def converter(original_report):
    report = rpt_fldr / original_report.name
    try:
        shutil.copyfile(original_report, report.absolute())
    except Exception as e:
        print(f"Download file failed on {report.name}.\n\n{e}", flush=True)
        return 0

    try:
        xml = report.stem + ".xml"
        command = subprocess.run(
            [
                str((Path(__file__).parent / "RptToXml" / "RptToXml.exe").absolute()),
                str(report.absolute()),
                str((xml_fldr / xml).absolute()),
            ],
            capture_output=True,
        )
        if command.stderr:
            print(
                f"Failed to convert {report.name}\n\n", str(command.stderr), flush=True
            )
            return 0

        report.unlink(missing_ok=True)

    except Exception as e:
        print(f"Failed to convert {report.name}.\n\n", str(e), flush=True)
        return 0

    return db_loader(xml_fldr / xml)
    return 0


def db_loader(xml):
    try:
        conn = pyodbc.connect(CRYSTALDATABASE, autocommit=True)
        cursor = conn.cursor()

        query_count = 0
        report = Report(str(xml.absolute()))
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

        conn.close()

        xml.unlink(missing_ok=True)

        return query_count

    except Exception as e:
        print(f"Failed to save {xml.name} to database.\n\n", str(e), flush=True)


def setup():
    conn = pyodbc.connect(CRYSTALDATABASE, autocommit=True)
    cursor = conn.cursor()

    cursor.execute("DELETE FROM [CrystalSQL].[dbo].[Templates] where 1=1;")
    conn.close()

    # remove report folder
    shutil.rmtree(rpt_fldr, ignore_errors=True)
    rpt_fldr.mkdir(exist_ok=True)

    # remove xml folder
    shutil.rmtree(xml_fldr, ignore_errors=True)
    xml_fldr.mkdir(exist_ok=True)


def printer(files, count):
    str_length = len(str(files))
    count_length = len(str(count))

    print(
        f"  - {count}{(str_length-count_length) * ' '} of {files} processed..",
        end="\r",
        flush=True,
    )


def main():
    start_time = time.time()

    worker_count = os.cpu_count() or 1
    if sys.platform == "win32":
        # Work around https://bugs.python.org/issue26903
        worker_count = min(worker_count, 60)

    print(f"{worker_count} cpu available.", flush=True)

    setup()

    duration = round(time.time() - start_time, 2)

    print(f"Finished setup in {duration} seconds.", flush=True)

    print("Setting up conversion..", flush=True)
    # convert all reports to xml
    start_time = time.time()
    count = 0
    query_count = 0
    files = list(Path(RTPSRC).glob("**/*.rpt"))
    file_count = len(files)
    with ProcessPoolExecutor(max_workers=worker_count) as exe:
        futures = {exe.submit(converter, this_file): this_file for this_file in files}

        print("Starting conversion..", flush=True)
        for future in as_completed(futures):
            count += 1
            if count % 50 == 0:
                printer(file_count, count)

            query_count += future.result() or 1

    duration = round(time.time() - start_time, 2)

    print(
        f"Loaded {query_count} queries from {count} reports in {duration} seconds.",
        flush=True,
    )


if __name__ == "__main__":
    main()
