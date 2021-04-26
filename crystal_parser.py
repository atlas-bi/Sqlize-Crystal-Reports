"""Sqlize Crystal Reports."""
# Sqlize Crystal Reports
# Copyright (C) 2020  Riverside Healthcare, Kankakee, IL

# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.

# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

import re

import sqlparse
from lxml import etree
from sqlize import Sqlize


class Report:
    """Class to parse the report xml."""

    def __init__(self, path):
        """Load the report as xml."""
        self.path = path
        parser = etree.XMLParser(ns_clean=True, recover=True)
        report_tree = etree.parse(path, parser=parser)

        self.database = None
        self.data_definition = None
        self.command_database_login = None
        self.command_database = None
        self.command = None

        self.root = report_tree.getroot()

        self.reports = self.root.find("SubReports").findall("Report")

    def title(self):
        """Get title."""
        return self.root.find("Summaryinfo").attrib["ReportTitle"]

    def description(self):
        """Get description."""
        return self.root.find("Summaryinfo").attrib["ReportComments"]

    def fields(self):
        """Get report fields."""
        fields = []
        for table in self.database.find("Tables").findall("Table"):
            for field in table.find("Fields").findall("Field"):
                fields.append(Sqlize(field.attrib["LongName"]).names())
        return "select " + ("\n,").join(fields) + " \n"

    def get_database(self):
        """Get database."""
        return self.command_database

    def get_database_login(self):
        """Get login."""
        return self.command_database_login

    def get_command(self):
        """Get command."""
        return self.command

    def joins(self):
        """Get sql joins."""
        tables = []
        for table in self.database.find("Tables").findall("Table"):
            if table.attrib["Alias"] == "Command":
                self.command_database = (
                    table.find("ConnectionInfo").attrib["QE_DatabaseName"]
                    if "QE_DatabaseName" in table.find("ConnectionInfo").attrib
                    else None
                )
                self.command_database_login = (
                    table.find("ConnectionInfo").attrib["QE_LogonProperties"]
                    if "QE_LogonProperties" in table.find("ConnectionInfo").attrib
                    else None
                )
            tables.append(
                {
                    table.attrib["Alias"]: table.attrib["Name"],
                    "CommandText": Sqlize(table.find("Command").text).sql()
                    if table.attrib["Alias"] == "Command"
                    else None,
                }
            )

        joins = []
        conditions = []
        join_tables = []
        rst = ""
        # pylint: disable=R1702
        for table_links in self.database.find("TableLinks").findall("TableLink"):
            if table_links.attrib["JoinType"] == "LeftOuter":
                join_type = table_links.attrib["JoinType"].replace(
                    "LeftOuter", "Left Outer Join"
                )
                for iteration, source_field in enumerate(
                    table_links.find("SourceFields").findall("Field")
                ):
                    # get table name
                    table = ""
                    for sql in tables:
                        for key, value in sql.items():
                            if (
                                key
                                == table_links.find("DestinationFields")[iteration]
                                .attrib["FormulaName"][1:-1]
                                .split(".")[0]
                            ):
                                table = value
                    join_type += (
                        " "
                        + table
                        + " as "
                        + table_links.find("DestinationFields")[iteration]
                        .attrib["FormulaName"][1:-1]
                        .split(".")[0]
                        + " on "
                        + source_field.attrib["FormulaName"][1:-1]
                        + " = "
                        + table_links.find("DestinationFields")[iteration].attrib[
                            "FormulaName"
                        ][1:-1]
                        + "\n"
                    )
                    join_tables.append(
                        source_field.attrib["FormulaName"][1:-1].split(".")[0]
                    )
                    join_tables.append(
                        table_links.find("DestinationFields")[iteration]
                        .attrib["FormulaName"][1:-1]
                        .split(".")[0]
                    )
                joins.append(join_type)
            else:
                for iteration, source_field in enumerate(
                    table_links.find("SourceFields").findall("Field")
                ):
                    join_type = (
                        source_field.attrib["FormulaName"][1:-1]
                        + " = "
                        + table_links.find("DestinationFields")[iteration].attrib[
                            "FormulaName"
                        ][1:-1]
                        + " /*"
                        + table_links.attrib["JoinType"]
                        + "*/ \n"
                    )
                    if rst == "":
                        rst += (
                            "from "
                            + source_field.attrib["FormulaName"][1:-1].split(".")[0]
                            + " \n"
                        )

                conditions.append(join_type)
        join_tables = list(dict.fromkeys(join_tables))

        # get tables that are not part of joins
        to_remove = []
        for sql in tables:
            for key, _value in sql.items():
                if key in join_tables:
                    to_remove.append(sql)

        for sql in to_remove:
            tables.remove(sql)

        for sql in tables:
            if rst == "":
                rst += " from "
            else:
                rst += ", "
                rst += (
                    "".join(
                        [
                            value + " as " + key
                            for key, value in dict(list(sql.items())[0:1]).items()
                        ]
                    )
                    + " "
                )

            if "Command" in sql:
                rst += "command as command"
                # if there is already a with, we need to string the withs.
                # else just wrap up the whole thing :)
                if not re.search(r"with", sql["CommandText"], flags=re.IGNORECASE):
                    self.command = (
                        "\n\r; with command as ("
                        + Sqlize(sql["CommandText"]).sql()
                        + ")\n\r "
                    )
                else:
                    # remove order by (cannot have in a with)
                    self.command = (
                        "\n\r" + Sqlize(sql["CommandText"]).sql_with() + "\n\r"
                    )

        rst += (" ").join(joins)
        if conditions + self.conditions():
            rst += "\n where " + ("\n and ").join(conditions + self.conditions())
        if self.sorts():
            rst += "\n order by " + "\n,".join(self.sorts())
        if self.groups():
            rst += "\n/* group by " + ",".join(self.groups()) + "*/ "
        rst += self.summary_fields()
        return rst

    def conditions(self):
        """Get conditions."""
        cond = []
        if self.data_definition.find("RecordSelectionFormula").text:
            cond.append(
                Sqlize(self.data_definition.find("RecordSelectionFormula").text).sql()
            )

        if self.data_definition.find("GroupSelectionFormula").text:
            cond.append(
                Sqlize(self.data_definition.find("GroupSelectionFormula").text).sql()
            )

        return cond

    def groups(self):
        """Get groups."""
        groups = []
        for group in self.data_definition.find("Groups").findall("Group"):
            groups.append(Sqlize(group.attrib["ConditionField"]).sql())
        return groups

    def sorts(self):
        """Get sorts."""
        sort = []
        for field in self.data_definition.find("SortFields").findall("SortField"):
            # pylint: disable=W0106
            sort.append(
                Sqlize(field.attrib["Field"]).names()
                + " "
                + Sqlize(field.attrib["SortDirection"]).sorts()
            ) if "SortDirection" in field.attrib else ""
        return sort

    def formulas(self):
        """Get formula."""
        formula = []
        for field in self.data_definition.find("FormulaFieldDefinitions").findall(
            "FormulaFieldDefinition"
        ):
            formula.append(
                " /* "
                + field.attrib["Name"]
                + (
                    " */ "
                    if "zz" not in field.attrib["Name"]
                    and "zx" not in field.attrib["Name"]
                    and "ShowPH" not in field.attrib["Name"]
                    else ""
                )
                + "DECLARE "
                + Sqlize(field.attrib["FormulaName"]).names()
                + " as "
                + Sqlize(field.attrib["ValueType"]).types()
                + " = "
                + (Sqlize(field.text).sql() if field.text else "")
                + (
                    " "
                    if "zz" not in field.attrib["Name"]
                    and "zx" not in field.attrib["Name"]
                    and "ShowPH" not in field.attrib["Name"]
                    else " */ "
                )
            )

        return ("\n\r").join(formula)

    def param_def(self):
        """Get parameter definitions."""
        # links to formula
        params = []
        if self.data_definition.find("ParameterFieldDefinitions") is not None:
            for field in self.data_definition.find("ParameterFieldDefinitions").findall(
                "ParameterFieldDefinition"
            ):
                parameter = (
                    "\n\r/* " + field.attrib["PromptText"] + " */\n\r "
                    if "PromptText" in field.attrib
                    else ""
                )
                if "FormulaName" in field.attrib:
                    parameter += (
                        "DECLARE "
                        + Sqlize(field.attrib["FormulaName"]).names()
                        + " as "
                        + Sqlize(field.attrib["ValueType"]).types()
                    )

                elif "Name" in field.attrib:
                    parameter += "/* " + field.attrib["Name"] + " */ "

                # inital value
                if field.find("ParameterInitialValues") is not None:
                    for value in field.find("ParameterInitialValues").findall(
                        "ParameterInitialValue"
                    ):
                        parameter += " = '" + value.attrib["Value"] + "'"
                    # values
                    for value in field.find("ParameterDefaultValues").findall(
                        "ParameterDefaultValue"
                    ):
                        if value.attrib["Value"]:
                            parameter += (
                                "/* "
                                + value.attrib["Value"]
                                + " "
                                + value.attrib["Description"]
                                + " */ "
                            )
                        else:
                            parameter += (
                                " = "
                                + value.attrib["Value"]
                                + " /* "
                                + value.attrib["Description"]
                                + " */ "
                            )

                params.append(parameter)
        return (" ").join(params) + " "

    def sql_expres(self):
        """Get sql expressions."""
        expres = []
        if self.data_definition.find("SQLExpressionFields") is not None:
            for formula in self.data_definition.find("SQLExpressionFields").findall(
                "SQLExpressionFieldDefinition"
            ):
                expres.append(
                    "; with "
                    + Sqlize(formula.attrib["FormulaName"]).names()
                    + " as ("
                    + Sqlize(formula.attrib["Text"]).sql()
                    + ") "
                )
        return ("\n\r").join(expres)

    def summary_fields(self):
        """Get sql summary fields."""
        sumf = []
        if self.data_definition.find("SummaryFields") is not None:
            for summary in self.data_definition.find("SummaryFields").findall(
                "SummaryFieldDefinition"
            ):
                sumf.append(Sqlize(summary.attrib["FormulaName"]).sql())

        if not sumf:
            return " /* summary fields: */ /* " + ("\n\r").join(sumf) + " */"
        return ""

    def sql(self):
        """Build sql."""
        sql_list = []

        search_area = [self.root]

        for report in self.reports:
            search_area.append(report)

        for xml in search_area:
            self.database = xml.find("Database")
            self.data_definition = xml.find("DataDefinition")
            self.command_database = ""
            self.command_database_login = ""
            self.command = ""

            # pylint: disable=C0301
            disclaimer = "/* caution: this report was parsed from a crystal report and may not run */\n "  # noqa: E501
            form = self.formulas()

            params = self.param_def()

            fields = self.fields()

            joins = self.joins()

            databases = (
                "use "
                + self.get_database()
                + "; --"
                + self.get_database_login()
                + "\n\r"
                if self.get_database()
                else ""
            )

            sql = (
                disclaimer
                + databases
                + params
                + self.sql_expres()
                + form
                + "\n\r"
                + self.get_command()
                + fields
                + joins
            )
            try:
                sql = sqlparse.format(
                    sql,
                    reindent=True,
                    keyword_case="lower",
                    identifier_case="lower",
                    comma_first=True,
                )

            except Exception:

                sql = sqlparse.format(
                    sql, keyword_case="lower", identifier_case="lower", comma_first=True
                )

            sql_list.append(
                sql.replace("/*", "\n/*").replace("*/", "*/\n").replace("\n\n", "\n")
            )

        return list(dict.fromkeys(sql_list))
