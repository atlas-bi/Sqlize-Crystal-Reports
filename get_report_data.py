"""Sqlize Crystal Reports."""

import collections

import pyodbc
import requests
import xmltodict
from dotenv import load_dotenv

load_dotenv()

SAPAPIURL = os.environ.get("SAPAPIURL", "http://my_boe.example.com")
SAPAPIUSERNAME = os.environ.get("SAPAPIUSERNAME", "BOE_REPORT")
SAPAPIPASSWORD = os.environ.get("SAPAPIPASSWORD", "12345")
CRYSTALDATABASE = os.environ.get(
    "CRYSTALDATABASE",
    "DRIVER={ODBC Driver 17 for SQL Server};SERVER=sqlServer;DATABASE=CrystalSQL;UID=joe;PWD=12345",
)

conn = pyodbc.connect(CRYSTALDATABASE, autocommit=True)
cursor = conn.cursor()


# get report id's from boe server. The report id's can be later used to generate
# run links for the reports.
# for more details see the sap docs: https://help.sap.com/viewer/0ef63ba725cd41a8ab4a69c226ec6b07/4.3.1/en-US/ec572a3c6fdb101497906a7cb0e91070.html
# remember, this is an xml string. if you have special chars in your password, encode them!
# for example, < encodes as &lt;


login_page = requests.post(
    f"{SAPAPIURL}:6405/biprws/logon/long",
    json={
        "userName": SAPAPIUSERNAME,
        "password": SAPAPIPASSWORD,
        "auth": "secEnterprise",
    },
    headers={"Content-Type": "application/json"},
)
# verify successful login
if "logonToken" not in login_page.text:
    raise ValueError(f"Failed to login:\n{login_page.text}")

headers = {"X-SAP-LogonToken": login_page.headers["X-SAP-LogonToken"]}

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
        f"{SAPAPIURL}:6405/biprws/raylight/v1/documents?offset={offset}&limit={batch_size}",
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
        f"{SAPAPIURL}:6405/biprws/raylight/v1/documents/{doc_id}/reports",
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
        f"{SAPAPIURL}:6405/biprws/bionbi/content/list?page={iteration}&pageSize={batch_size}",
        headers=headers,
    )

    if "entry" in xmltodict.parse(batch.text)["feed"]:
        docs = xmltodict.parse(batch.text)["feed"]["entry"]

        size = len(docs)

        for doc in docs:
            # skip non dict
            if type(doc) != collections.OrderedDict:
                continue
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
    requests.post(f"{SAPAPIURL}:6405/biprws/logoff", headers=headers)
except BaseException as e:
    print(str(e))

conn.close()
