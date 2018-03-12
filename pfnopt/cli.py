from argparse import ArgumentParser  # NOQA
from argparse import Namespace  # NOQA
from cliff.app import App
from cliff.command import Command
from cliff.commandmanager import CommandManager
import sys

from pfnopt.storage import RDBStorage
from pfnopt.study import create_new_study


class PFNOptApp(App):

    def __init__(self):
        super(PFNOptApp, self).__init__(
            description='',
            version='0.0.1',
            command_manager=CommandManager('pfnopt.command')
        )


class MakeStudy(Command):

    def get_parser(self, prog_name):
        # type: (str) -> ArgumentParser
        parser = super(MakeStudy, self).get_parser(prog_name)
        parser.add_argument('--url', '-u', dest='url', required=True)
        return parser

    def take_action(self, parsed_args):
        # type: (Namespace) -> None
        storage = RDBStorage(parsed_args.url)
        study_uuid = create_new_study(storage).study_uuid
        print(study_uuid)


def main():
    return PFNOptApp().run(sys.argv[1:])
