<h1 align="center">Sqlize Crystal Reports</h1>
<h4 align="center">Atlas BI Library ETL | Crystal Reports Supplimentary ETL</h4>
<p align="center">
 <a href="https://www.atlas.bi" target="_blank">Website</a> • <a href="https://demo.atlas.bi" target="_blank">Demo</a> • <a href="https://www.atlas.bi/docs/bi-library/" target="_blank">Documentation</a> • <a href="https://discord.gg/hdz2cpygQD" target="_blank">Chat</a>
</p>
<p align="center">
<a href="https://www.codacy.com/gh/Riverside-Healthcare/Tableau-Metadata-Exporter/dashboard?utm_source=github.com&amp;utm_medium=referral&amp;utm_content=Riverside-Healthcare/Tableau-Metadata-Exporter&amp;utm_campaign=Badge_Grade"><img alt="codacy" src="https://app.codacy.com/project/badge/Grade/cc6a57cbb8f74e5caa103abc1316e904"></a>
 <a href="https://sonarcloud.io/project/overview?id=atlas-bi_Sqlize-Crystal-Reports"><img alt="maintainability" src="https://sonarcloud.io/api/project_badges/measure?project=atlas-bi_Sqlize-Crystal-Reports&metric=sqale_rating"></a>
 <a href="https://discord.gg/hdz2cpygQD"><img alt="discord chat" src="https://badgen.net/discord/online-members/hdz2cpygQD/" /></a>
 <a href="https://github.com/atlas-bi/Sqlize-Crystal-Reports/releases"><img alt="latest release" src="https://badgen.net/github/release/atlas-bi/Sqlize-Crystal-Reports" /></a>

<p align="center">Make a wild swing at converting Crystal Reports into SQL and extracting useful metadata.
 </p>

## 🔧 How Does it Work?
**Sqlize Crystal Reports** runs [Aidan Ryan's](https://github.com/ajryan) [RptToXml](https://github.com/ajryan/RptToXml) converter to convert a directory of SAP Crystal Reports into XLM files, and then makes a strong attempt at parsing that XML out into a *somewhat* readable and *potentially* runnable t-sql statement. The results are saved into a database table along with the reports:


  * FileName
  * Title
  * Description
  * Query

If mutliple queries are found in the report, there will be a db entry for each query.

:construction_worker: Please chip in if you see a way to make the sql more runnable or code more readable.

 > good luck from here :smirk:



## 🏃 Getting Started

### First, install SAP's Crystal Reports, Developer for Visual Studio, SP 28

Here are a few links to try -

* [Direct link to download https://www.sap.com/cmp/td/sap-crystal-reports-visual-studio-trial.html](https://www.sap.com/cmp/td/sap-crystal-reports-visual-studio-trial.html)
* [How To Page https://wiki.scn.sap.com/wiki/display/BOBJ/Crystal+Reports%2C+Developer+for+Visual+Studio+Downloads](https://wiki.scn.sap.com/wiki/display/BOBJ/Crystal+Reports%2C+Developer+for+Visual+Studio+Downloads)
* [Wiki Home https://blogs.sap.com/2016/12/06/sap-crystal-reports-developer-version-for-microsoft-visual-studio-updates-runtime-downloads/](https://blogs.sap.com/2016/12/06/sap-crystal-reports-developer-version-for-microsoft-visual-studio-updates-runtime-downloads/)

We are on a 64bit Windows Machine and built the executable with the 64 drivers. If you are on a 32bit machine you might as well rebuild from the source.
Install:

  * SAP Crystal Reports for Visual Studio (SP28) runtime engine for .NET framework MSI (64-bit)
  * SAP Crystal Reports for Visual Studio (SP28) runtime (64-bit)

 > Maybe the 2nd install is redundant?

### Next, install a few Python packages

```sh
pip install pyodbc lxml sqlparse requests xmltodict
```

### Create Database

There are a few tables to create -

```sql
USE [CrystalSQL]
GO

SET ANSI_NULLS ON
GO

SET QUOTED_IDENTIFIER ON
GO


CREATE TABLE [dbo].[Reports](
  [Name] [nvarchar](max) NULL,
  [Reference] [nvarchar](max) NULL,
  [ReportId] [nvarchar](max) NULL,
  [DocumentId] [nvarchar](max) NULL
) ON [PRIMARY] TEXTIMAGE_ON [PRIMARY]
GO

CREATE TABLE [dbo].[Templates](
  [ReportName] [nvarchar](max) NULL,
  [Query] [text] NULL,
  [Title] [nvarchar](max) NULL,
  [Description] [nvarchar](max) NULL
) ON [PRIMARY] TEXTIMAGE_ON [PRIMARY]
GO

CREATE TABLE [dbo].[Attachments](
  [HRX] [nvarchar](max) NULL,
  [PDF] [nvarchar](max) NULL,
  [CreationDate] [datetime] NULL,
  [Name] [nvarchar](max) NULL
) ON [PRIMARY] TEXTIMAGE_ON [PRIMARY]
GO

CREATE TABLE [dbo].[Documents](
  [Name] [nvarchar](max) NULL,
  [Description] [nvarchar](max) NULL,
  [FolderId] [nvarchar](max) NULL,
  [Cuid] [nvarchar](max) NULL,
  [DocumentId] [nvarchar](max) NULL
) ON [PRIMARY] TEXTIMAGE_ON [PRIMARY]
GO

CREATE TABLE [dbo].[Objects](
  [Title] [nvarchar](max) NULL,
  [Cuid] [nvarchar](max) NULL,
  [StatusType] [nvarchar](max) NULL,
  [Type] [nvarchar](max) NULL,
  [LastRun] [nvarchar](max) NULL
) ON [PRIMARY] TEXTIMAGE_ON [PRIMARY]
GO
```

Don't forget to add a user account that can delete and insert.

### Create .env file

(or, pass the variables as environment variables)

```py
database = 'DRIVER={ODBC Driver 17 for SQL Server};SERVER=server_name;DATABASE=database_name;UID=username;PWD=password'

# get report sql settings
rpt_src = '\\\\network\\c$\\path\\to\\.rpt\\files\\'

# get report data settings
sap_api_username = "BOE_REPORT"
sap_api_password = "password"
sap_api_url = "http://server.example.net"

# get report files settings
crystal_boe_output_drive = "\\\\server\\Output"
```

### Running

There are three parts to this ETL that can be run separately.
```sh
python get_report_data.py # loads BOE report links
python get_sql.py # gets report sql code
python get_report_files.py # gets report output links. passed to Atlas as run links
```
## 🏆 Credits

Special thanks to [Aidan Ryan](https://github.com/ajryan) for creating the [RptToXml](https://github.com/ajryan/RptToXml) converter.
