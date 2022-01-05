[![Maintainability](https://api.codeclimate.com/v1/badges/a325744e35ae6c5ec9b5/maintainability)](https://codeclimate.com/github/Riverside-Healthcare/Sqlize-Crystal-Reports/maintainability)
[![Codacy Badge](https://app.codacy.com/project/badge/Grade/cc6a57cbb8f74e5caa103abc1316e904)](https://www.codacy.com/gh/Riverside-Healthcare/Sqlize-Crystal-Reports/dashboard?utm_source=github.com&amp;utm_medium=referral&amp;utm_content=Riverside-Healthcare/Sqlize-Crystal-Reports&amp;utm_campaign=Badge_Grade)
[![CodeQL](https://github.com/Riverside-Healthcare/Sqlize-Crystal-Reports/actions/workflows/codeql-analysis.yml/badge.svg)](https://github.com/Riverside-Healthcare/Sqlize-Crystal-Reports/actions/workflows/codeql-analysis.yml)

# Sqlize Crystal Reports

## About

**Sqlize Crystal Reports** runs [Aidan Ryan's](https://github.com/ajryan) [RptToXml](https://github.com/ajryan/RptToXml) converter to convert a directory of SAP Crystal Reports into XLM files, and then makes a strong attempt at parsing that XML out into a *somewhat* readable and *potentially* runnable t-sql statement. The results are saved into a database table along with the reports:

  * FileName
  * Title
  * Description
  * Query

If mutliple queries are found in the report, there will be a db entry for each query.

:construction_worker: Please chip in if you see a way to make the sql more runnable or code more readable.

 > good luck from here :smirk:

## Credits

Special thanks to [Aidan Ryan](https://github.com/ajryan) for creating the [RptToXml](https://github.com/ajryan/RptToXml) converter.

Sqlize Crystal Reports was created by the Riverside Healthcare Analytics team -

  * Paula Courville
  * [Darrel Drake](https://www.linkedin.com/in/darrel-drake-57562529)
  * [Dee Anna Hillebrand](https://github.com/DHillebrand2016)
  * [Scott Manley](https://github.com/Scott-Manley)
  * [Madeline Matz](mailto:mmatz@RHC.net)
  * [Christopher Pickering](https://github.com/christopherpickering)
  * [Dan Ryan](https://github.com/danryan1011)
  * [Richard Schissler](https://github.com/schiss152)
  * [Eric Shultz](https://github.com/eshultz)

## How To Run

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
pip install pyodbc lxml sqlparse
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

### Create settings.py file

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
