"""
  Sqlize Crystal Reports
  Copyright (C) 2020  Riverside Healthcare, Kankakee, IL

  This program is free software: you can redistribute it and/or modify
  it under the terms of the GNU General Public License as published by
  the Free Software Foundation, either version 3 of the License, or
  (at your option) any later version.

  This program is distributed in the hope that it will be useful,
  but WITHOUT ANY WARRANTY; without even the implied warranty of
  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
  GNU General Public License for more details.

  You should have received a copy of the GNU General Public License
  along with this program.  If not, see <https://www.gnu.org/licenses/>.

"""

from pathlib import Path, PureWindowsPath
import shutil
import subprocess
import pyodbc
import settings

rpt_fldr = str(Path(__file__).parent.absolute()) + "\\crystal_rpt\\"
xml_fldr = str(Path(__file__).parent.absolute()) + "\\crystal_xml\\"

# remove report folder
shutil.rmtree(rpt_fldr, ignore_errors=True)
Path(rpt_fldr).mkdir(exist_ok=True)

# copy in reports
for f in Path(settings.rpt_src).glob("*.rpt"):
    shutil.copyfile(settings.rpt_src + f.name, rpt_fldr + f.name)

# remove xml folder
shutil.rmtree(xml_fldr, ignore_errors=True)
Path(xml_fldr).mkdir(exist_ok=True)

# convert all reports to xml
for f in Path(rpt_fldr).glob("*.rpt"):
    # if there are a ton of reports using threading might speed things up!
    try:
        x =subprocess.run(
            [
                str(
                    PureWindowsPath(
                        str(Path(__file__).parent.absolute()) + "\\RptToXml\\RptToXml.exe"
                    )
                ),
                str(PureWindowsPath(rpt_fldr + f.name)),
                str(PureWindowsPath(xml_fldr + f.stem)) + ".xml",
            ],
            capture_output=True 
        )
        if x.stderr:
            print(f.name, str(x.stderr))

    except Exception as e:
        print(f.name, str(e))
        continue



from crystal_parser import report

conn = pyodbc.connect(settings.database, autocommit=True)
cursor = conn.cursor()

cursor.execute("DELETE FROM [CrystalSQL].[dbo].[Query] where 1=1;")

for f in Path(xml_fldr).glob("*.xml"):

    try:
        t = report(xml_fldr + f.name)
        title = t.title()
        description = t.description()

        for s in t.sql():
            cursor.execute(
                "INSERT INTO [CrystalSQL].[dbo].[Query] (ReportName,Query,Title,Description) VALUES (?,?,?,?)",
                f.stem + ".rpt",
                s,
                title,
                description,
            )

    except Exception as e:
        print(f.name, str(e))

conn.close()
