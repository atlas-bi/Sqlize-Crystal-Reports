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

from lxml import etree
import re
import sqlparse
from sqlize import sqlize


class report:
    def __init__(self, path):
        self.path = path
        parser = etree.XMLParser(ns_clean=True, recover=True)
        e = etree.parse(path, parser=parser)

        self.root = e.getroot()

        self.reports = self.root.find("SubReports").findall("Report")

    def title(self):
        return self.root.find("Summaryinfo").attrib["ReportTitle"]

    def description(self):
        return self.root.find("Summaryinfo").attrib["ReportComments"]

    def fields(self):
        fields = []
        for t in self.Database.find("Tables").findall("Table"):
            for f in t.find("Fields").findall("Field"):
                fields.append(sqlize(f.attrib["LongName"]).names())
        return "select " + ("\n,").join(fields) + " \n"

    def database(self):
        return self.CommandDatabase

    def databaseLogin(self):
        return self.CommandDatabaseLogin

    def command(self):
        return self.Command

    def joins(self):

        tables = []
        for t in self.Database.find("Tables").findall("Table"):
            if t.attrib["Alias"] == "Command":
                self.CommandDatabase = (
                    t.find("ConnectionInfo").attrib["QE_DatabaseName"]
                    if "QE_DatabaseName" in t.find("ConnectionInfo").attrib
                    else None
                )
                self.CommandDatabaseLogin = (
                    t.find("ConnectionInfo").attrib["QE_LogonProperties"]
                    if "QE_LogonProperties" in t.find("ConnectionInfo").attrib
                    else None
                )
            tables.append(
                {
                    t.attrib["Alias"]: t.attrib["Name"],
                    "CommandText": sqlize(t.find("Command").text).sql()
                    if t.attrib["Alias"] == "Command"
                    else None,
                }
            )

        joins = []
        conditions = []
        join_tables = []
        rst = ""
        for t in self.Database.find("TableLinks").findall("TableLink"):
            if t.attrib["JoinType"] == "LeftOuter":
                val = t.attrib["JoinType"].replace("LeftOuter", "Left Outer Join")
                for x, s in enumerate(t.find("SourceFields").findall("Field")):
                    # get table name
                    table = ""
                    for q in tables:
                        for key, value in q.items():
                            if (
                                key
                                == t.find("DestinationFields")[x]
                                .attrib["FormulaName"][1:-1]
                                .split(".")[0]
                            ):
                                table = value
                    val += (
                        " "
                        + table
                        + " as "
                        + t.find("DestinationFields")[x]
                        .attrib["FormulaName"][1:-1]
                        .split(".")[0]
                        + " on "
                        + s.attrib["FormulaName"][1:-1]
                        + " = "
                        + t.find("DestinationFields")[x].attrib["FormulaName"][1:-1]
                        + "\n"
                    )
                    join_tables.append(s.attrib["FormulaName"][1:-1].split(".")[0])
                    join_tables.append(
                        t.find("DestinationFields")[x]
                        .attrib["FormulaName"][1:-1]
                        .split(".")[0]
                    )
                joins.append(val)
            else:
                for x, s in enumerate(t.find("SourceFields").findall("Field")):
                    val = (
                        s.attrib["FormulaName"][1:-1]
                        + " = "
                        + t.find("DestinationFields")[x].attrib["FormulaName"][1:-1]
                        + " /*"
                        + t.attrib["JoinType"]
                        + "*/ \n"
                    )
                    if rst == "":
                        rst += (
                            "from "
                            + s.attrib["FormulaName"][1:-1].split(".")[0]
                            + " \n"
                        )

                conditions.append(val)
        join_tables = list(dict.fromkeys(join_tables))

        # get tables that are not part of joins
        to_remove = []
        for t in tables:
            for key, value in t.items():
                if key in join_tables:
                    to_remove.append(t)
        [tables.remove(x) for x in to_remove]

        for t in tables:
            if rst == "":
                rst += " from "
            else:
                rst += ", "
                rst += (
                    "".join(
                        [
                            value + " as " + key
                            for key, value in dict(list(t.items())[0:1]).items()
                        ]
                    )
                    + " "
                )

            if "Command" in t:
                rst += "command as command"
                # if there is already a with, we need to string the withs. else just wrap up the whole thing :)
                if not re.search(r"with", t["CommandText"], flags=re.IGNORECASE):
                    self.Command = (
                        "\n\r; with command as ("
                        + sqlize(t["CommandText"]).sql()
                        + ")\n\r "
                    )
                else:
                    # remove order by (cannot have in a with)
                    self.Command = "\n\r" + sqlize(t["CommandText"]).sqlWith() + "\n\r"

        rst += (" ").join(joins)
        if conditions + self.conditions():
            rst += "\n where " + ("\n and ").join(conditions + self.conditions())
        if self.sorts():
            rst += "\n order by " + "\n,".join(self.sorts())
        if self.groups():
            rst += "\n/* group by " + ",".join(self.groups()) + "*/ "
        rst += self.summaryFields()
        return rst

    def conditions(self):

        cond = []
        if self.DataDefinition.find("RecordSelectionFormula").text:
            cond.append(
                sqlize(self.DataDefinition.find("RecordSelectionFormula").text).sql()
            )

        if self.DataDefinition.find("GroupSelectionFormula").text:
            cond.append(
                sqlize(self.DataDefinition.find("GroupSelectionFormula").text).sql()
            )

        return cond

    def groups(self):
        group = []
        for g in self.DataDefinition.find("Groups").findall("Group"):
            group.append(sqlize(g.attrib["ConditionField"]).sql())
        return group

    def sorts(self):
        sort = []
        for s in self.DataDefinition.find("SortFields").findall("SortField"):
            sort.append(
                sqlize(s.attrib["Field"]).names()
                + " "
                + sqlize(s.attrib["SortDirection"]).sorts()
            ) if "SortDirection" in s.attrib else ""
        return sort

    def formulas(self):
        formula = []
        for f in self.DataDefinition.find("FormulaFieldDefinitions").findall(
            "FormulaFieldDefinition"
        ):
            formula.append(
                " /* "
                + f.attrib["Name"]
                + (" */ " if 'zz' not in f.attrib["Name"] and 'zx' not in f.attrib["Name"] and 'ShowPH' not in f.attrib["Name"] else '')
                + "DECLARE "
                + sqlize(f.attrib["FormulaName"]).names()
                + " as "
                + sqlize(f.attrib["ValueType"]).types()
                + " = "
                + (sqlize(f.text).sql()
                if f.text
                else "")
                + (" " if 'zz' not in f.attrib["Name"] and 'zx' not in f.attrib["Name"] and 'ShowPH' not in f.attrib["Name"] else ' */ ')
            )
          
        return ("\n\r").join(formula)

    def groupDef(self):
        for f in self.DataDefinition.find("GroupNameFieldDefinitions").findall(
            "GroupNameFieldDefinition"
        ):
            print(
                f.attrib["FormulaName"]
                + " "
                + f.attrib["ValueType"]
                + " "
                + f.attrib["Name"]
            )

    def paramDef(self):
        # links to formula
        params = []
        if self.DataDefinition.find("ParameterFieldDefinitions") is not None:
            for f in self.DataDefinition.find("ParameterFieldDefinitions").findall(
                "ParameterFieldDefinition"
            ):
                val = (
                    "\n\r/* " + f.attrib["PromptText"] + " */\n\r "
                    if "PromptText" in f.attrib
                    else ""
                )
                if "FormulaName" in f.attrib:
                    val += (
                        "DECLARE "
                        + sqlize(f.attrib["FormulaName"]).names()
                        + " as "
                        + sqlize(f.attrib["ValueType"]).types()
                    )

                elif "Name" in f.attrib:
                    val += "/* " + f.attrib["Name"] + " */ "

                # inital value
                if f.find("ParameterInitialValues") is not None:
                    for v in f.find("ParameterInitialValues").findall(
                        "ParameterInitialValue"
                    ):
                        val += " = '" + v.attrib["Value"] + "'"
                    # values
                    for v in f.find("ParameterDefaultValues").findall(
                        "ParameterDefaultValue"
                    ):
                        if v.attrib["Value"]:
                            val += (
                                "/* "
                                + v.attrib["Value"]
                                + " "
                                + v.attrib["Description"]
                                + " */ "
                            )
                        else:
                            val += (
                                " = "
                                + v.attrib["Value"]
                                + " /* "
                                + v.attrib["Description"]
                                + " */ "
                            )

                params.append(val)
        return (" ").join(params) + " "

    def sqlExpres(self):
        expres = []
        if self.DataDefinition.find("SQLExpressionFields") is not None:
            for f in self.DataDefinition.find("SQLExpressionFields").findall(
                "SQLExpressionFieldDefinition"
            ):
                expres.append(
                    "; with "
                    + sqlize(f.attrib["FormulaName"]).names()
                    + " as ("
                    + sqlize(f.attrib["Text"]).sql()
                    + ") "
                )
        return ("\n\r").join(expres)

    def summaryFields(self):
        sumf = []
        if self.DataDefinition.find("SummaryFields") is not None:
            for s in self.DataDefinition.find("SummaryFields").findall(
                "SummaryFieldDefinition"
            ):
                sumf.append(sqlize(s.attrib["FormulaName"]).sql())

        if len(sumf):
            return " /* summary fields: */ /* " + ("\n\r").join(sumf) + " */"
        return ""

    def sql(self):

        sql_list = []

        search_area = [self.root]
        [search_area.append(x) for x in self.reports]

        for x in search_area:
            self.Database = x.find("Database")
            self.DataDefinition = x.find("DataDefinition")
            self.CommandDatabase = ""
            self.CommandDatabaseLogin = ""
            self.Command = ""

            disclaimer = "/* caution: this report was parsed from a crystal report and may not run */\n "
            form = self.formulas()
            #print(form)
            p = self.paramDef()
            # print(p)
            f = self.fields()
            # print(f)
            j = self.joins()
            # print(j)
            d = (
                "use " + self.database() + "; --" + self.databaseLogin() + "\n\r"
                if self.database()
                else ""
            )
            # print(d)
            # print(self.sqlExpres())
            # print(self.command())
            sql = (
                disclaimer
                + d
                + p
                + self.sqlExpres()
                + form
                + "\n\r"
                + self.command()
                + f
                + j
            )
            try:
                sql = sqlparse.format(
                    sql,
                    reindent=True,
                    keyword_case="lower",
                    identifier_case="lower",
                    comma_first=True,
                )
            except Exception as e:
                # print(self.path + ": error: ", str(e))
                sql = sqlparse.format(
                    sql, keyword_case="lower", identifier_case="lower", comma_first=True
                )
            #print(sql)
            sql_list.append(
                sql.replace("/*", "\n/*").replace("*/", "*/\n").replace("\n\n", "\n")
            )

        return list(dict.fromkeys(sql_list))
