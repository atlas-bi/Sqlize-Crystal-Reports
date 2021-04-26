"""Convert crystal items to sql items."""
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


class Sqlize:
    """Converty crystal items to sql items."""

    def __init__(self, cmd):
        """Load sql."""
        self.cmd = cmd

    def sql(self):
        """Process and return sql."""
        self.__clean_params()
        self.__clean_comments()
        self.__clean_query()

        return self.cmd

    def sql_with(self):
        """Cleanup sql with command."""
        self.cmd = self.sql()

        # with (select...) cannot have order by
        # remove order by

        self.cmd = re.sub(
            r"order by [\w+\.?\w+,?\s?\w?]+$", "", self.cmd, flags=re.IGNORECASE
        )

        # wrap with paren and add select

        self.cmd = (
            re.sub(
                r"(?<=\))[^\(\)]+?(select)",
                lambda m: ", command as (" + m.group(1),
                self.cmd,
                flags=re.IGNORECASE,
            )
            + ") "
        )

        return self.cmd

    def names(self):
        """Cleanup variable names."""
        self.__clean_names()

        return self.cmd

    def types(self):
        """Cleanup data types."""
        return (
            self.cmd.replace("DateField", "date")
            .replace("StringField", "varchar(max)")
            .replace("DateTimeField", "datetime")
            .replace("NumberField", "decimal(5,2)")
            .replace("BooleanField", "varchar(5)")
        )  # field is typically defaulted to true or false

    def sorts(self):
        """Cleanup sorts."""
        return self.cmd.replace("AscendingOrder", "asc").replace(
            "DescendingOrder", "desc"
        )

    def __clean_names(self):
        """Cleanup variable names."""
        self.cmd = re.sub(r"[\?%@]", "@", self.cmd)
        self.cmd = re.sub(
            r"@?[^a-zA-Z0-9_.]+", "", self.cmd.replace(" ", "_").replace("-", "_")
        )
        self.cmd = re.sub(r"[{}]", "", self.cmd)

    def __clean_params(self):
        """Cleanup parameters."""
        # Fix column alias.
        # select x as "this is cool" > select x as this_is_cool

        self.cmd = re.sub(
            r"as ({\'.+?\'})",
            lambda m: "as "
            + re.sub(
                r"[^a-zA-Z0-9_.]+", "", m.group(1).replace(" ", "_").replace("-", "_")
            ),
            self.cmd,
            flags=re.IGNORECASE,
        )

        # clean up paramter names
        # select {?my ugly var!} > select @my_ugly_var

        self.cmd = re.sub(
            r"{[\?@%](.+?)}",
            lambda m: "@"
            + re.sub(
                r"[^a-zA-Z0-9_.]+", "", m.group(1).replace(" ", "_").replace("-", "_")
            ).replace(" ", "_"),
            self.cmd,
        )

    def __clean_comments(self):
        """Change comment style sql."""
        self.cmd = self.cmd.replace("//", "--")

    def __clean_query(self):
        """Cleanup query syntax."""
        # remove use clause
        self.cmd = re.sub(r"[;|\s]?use .+?[;|\s|$]", "", self.cmd, flags=re.IGNORECASE)

        # remove brakets
        self.cmd = re.sub(r"[{}]", "", self.cmd)

        # update symbols
        self.cmd = re.sub(r"\s[\?%]", " @", self.cmd)

        # remove extra text
        self.cmd = self.cmd.replace("distinctcount_", "")
        self.cmd = re.sub(
            r"distinctcount_", lambda m: " /* " + m.group(0) + " */ ", self.cmd
        )
