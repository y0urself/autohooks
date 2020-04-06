# Copyright (C) 2019-2020 Greenbone Networks GmbH
#
# SPDX-License-Identifier: GPL-3.0-or-later
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
import argparse
import re
import sys

from pathlib import Path
from typing import Union

import tomlkit

from packaging.version import Version, InvalidVersion

from autohooks.__version__ import __version__ as _current_version


class VersionError(Exception):
    """
    Some error has occurred during version handling
    """


def get_version() -> str:
    """
    Returns the current version of autohooks
    """
    return _current_version


def strip_version(version: str) -> str:
    """
    Strips a leading 'v' from a version string

    E.g. v1.2.3 will be converted to 1.2.3
    """
    if version and version[0] == 'v':
        return version[1:]

    return version


def safe_version(version: str) -> str:
    """
    Returns the version as a string in `PEP440`_ compliant
    format.

    .. _PEP440:
       https://www.python.org/dev/peps/pep-0440
    """
    try:
        return str(Version(version))
    except InvalidVersion:
        version = version.replace(' ', '.')
        return re.sub('[^A-Za-z0-9.]+', '-', version)


def get_version_from_pyproject_toml(pyproject_toml_path: Path = None) -> str:
    """
    Return the version information from the [tool.poetry] section of the
    pyproject.toml file. The version may be in non standardized form.
    """
    if not pyproject_toml_path:
        path = Path(__file__)
        pyproject_toml_path = path.parent.parent / 'pyproject.toml'

    if not pyproject_toml_path.exists():
        raise VersionError(
            '{} file not found.'.format(str(pyproject_toml_path))
        )

    pyproject_toml = tomlkit.parse(pyproject_toml_path.read_text())
    if (
        'tool' in pyproject_toml
        and 'poetry' in pyproject_toml['tool']
        and 'version' in pyproject_toml['tool']['poetry']
    ):
        return pyproject_toml['tool']['poetry']['version']

    raise VersionError(
        'Version information not found in {} file.'.format(
            str(pyproject_toml_path)
        )
    )


def versions_equal(new_version: str, old_version: str) -> bool:
    """
    Checks if new_version and old_version are equal
    """
    return safe_version(old_version) == safe_version(new_version)


def is_version_pep440_compliant(version: str) -> bool:
    """
    Checks if the provided version is a PEP 440 compliant version string
    """
    return version == safe_version(version)


class VersionCommand:
    TEMPLATE = """# pylint: disable=invalid-name

# THIS IS AN AUTOGENERATED FILE. DO NOT TOUCH!

__version__ = "{}"\n"""

    name = 'autohooks'
    version_file_path = Path.cwd() / 'autohooks' / '__version__.py'
    pyproject_toml_path = Path.cwd() / 'pyproject.toml'

    def __init__(
        self,
        *,
        version_file_path: Path = None,
        pyproject_toml_path: Path = None,
        name: str = None
    ):
        if version_file_path:
            self.version_file_path = version_file_path

        if pyproject_toml_path:
            self.pyproject_toml_path = pyproject_toml_path

        if name:
            self.name = name

        self._configure_parser()

    def _configure_parser(self):
        self.parser = argparse.ArgumentParser(
            description='Version handling utilities for {}.'.format(self.name),
            prog='version',
        )

        subparsers = self.parser.add_subparsers(
            title='subcommands',
            description='valid subcommands',
            help='additional help',
            dest='command',
        )

        verify_parser = subparsers.add_parser('verify')
        verify_parser.add_argument('version', help='version string to compare')

        subparsers.add_parser('show')

        update_parser = subparsers.add_parser('update')
        update_parser.add_argument('version', help='version string to use')
        update_parser.add_argument(
            '--force',
            help="don't check if version is already set",
            action="store_true",
        )

    def _print(self, *args) -> None:
        print(*args)

    def get_current_version(self) -> str:
        raise NotImplementedError()

    def update_version_file(self, new_version: str) -> None:
        """
        Update the version file with the new version
        """
        version = safe_version(new_version)

        self.version_file_path.write_text(self.TEMPLATE.format(version))

    def update_pyproject_version(self, new_version: str,) -> None:
        """
        Update the version in the pyproject.toml file
        """
        version = safe_version(new_version)

        pyproject_toml = tomlkit.parse(self.pyproject_toml_path.read_text())

        if 'tool' not in pyproject_toml:
            tool_table = tomlkit.table()
            pyproject_toml['tool'] = tool_table

        if 'poetry' not in pyproject_toml['tool']:
            poetry_table = tomlkit.table()
            pyproject_toml['tool'].add('poetry', poetry_table)

        pyproject_toml['tool']['poetry']['version'] = version

        self.pyproject_toml_path.write_text(tomlkit.dumps(pyproject_toml))

    def update_version(self, new_version: str, *, force: bool = False) -> None:
        if not self.pyproject_toml_path.exists():
            raise VersionError(
                'Could not find {} file.'.format(str(self.pyproject_toml_path))
            )

        pyproject_version = get_version_from_pyproject_toml(
            pyproject_toml_path=self.pyproject_toml_path
        )

        if not self.version_file_path.exists():
            raise VersionError(
                'Could not find {} file.'.format(str(self.version_file_path))
            )

        if not force and versions_equal(
            new_version, self.get_current_version()
        ):
            self._print('Version is already up-to-date.')
            return

        self.update_pyproject_version(new_version=new_version,)

        self.update_version_file(new_version=new_version)

        self._print(
            'Updated version from {} to {}'.format(
                pyproject_version, safe_version(new_version)
            )
        )

    def verify_version(self, version: str) -> None:
        current_version = self.get_current_version()
        if not is_version_pep440_compliant(current_version):
            raise VersionError(
                "The version {} in {} is not PEP 440 compliant.".format(
                    current_version, str(self.version_file_path)
                )
            )

        pyproject_version = get_version_from_pyproject_toml(
            pyproject_toml_path=self.pyproject_toml_path
        )

        if pyproject_version != current_version:
            raise VersionError(
                "The version {} in {} doesn't match the current "
                "version {}.".format(
                    pyproject_version,
                    str(self.pyproject_toml_path),
                    current_version,
                )
            )

        if version != 'current':
            provided_version = strip_version(version)
            if provided_version != current_version:
                raise VersionError(
                    "Provided version {} does not match the current "
                    "version {}.".format(provided_version, current_version)
                )

        self._print('OK')

    def print_current_version(self) -> None:
        self._print(self.get_current_version())

    def run(self) -> Union[int, str]:
        args = self.parser.parse_args()

        if not getattr(args, 'command', None):
            self.parser.print_usage()
            return 0

        try:
            if args.command == 'update':
                self.update_version(
                    args.version, force=args.force,
                )
            elif args.command == 'show':
                self.print_current_version()
            elif args.command == 'verify':
                self.verify_version(args.version)
        except VersionError as e:
            return str(e)

        return 0


class AutohooksVersionCommand(VersionCommand):

    name = 'autohooks'
    version_file_path = Path.cwd() / 'autohooks' / '__version__.py'
    pyproject_toml_path = Path.cwd() / 'pyproject.toml'

    def get_current_version(self):
        return _current_version


def main():
    cmd = AutohooksVersionCommand()
    sys.exit(cmd.run())


if __name__ == '__main__':
    main()
