#!/usr/bin/env python3
#
# ls for inside of zipfile

# TODO: handle globbing, wildcards, e.g. * ?

import argparse
import datetime
import math
import pathlib
import re
import shutil
import sys
import zipfile


TERM_COLS = shutil.get_terminal_size(fallback=(80,24))[0]

# quick and dirty (hack) terminal color codes
BLACK = "\u001b[30m"
RED = "\u001b[31m"
GREEN = "\u001b[32m"
YELLOW = "\u001b[33m"
BLUE = "\u001b[34m"
MAGENTA = "\u001b[35m"
CYAN = "\u001b[36m"
WHITE = "\u001b[37m"
RESET = "\u001b[0m"

# Custom error to indicate no such file or directory
#   (differentiating from finding an empty directory with no contents)
class NoSuchFileDirError(Exception):
    pass


def process_command_line(argv):
    """Process command line invocation arguments and switches.

    Args:
        argv: list of arguments, or `None` from ``sys.argv[1:]``.

    Returns:
        args: Namespace with named attributes of arguments and switches
    """
    #script_name = argv[0]
    argv = argv[1:]

    # initialize the parser object:
    parser = argparse.ArgumentParser(
            description="ls inside of a zipfile.")

    # specifying nargs= puts outputs of parser in list (even if nargs=1)

    # required arguments
    parser.add_argument('zipfile',
            help="Path to zipfile.",
            )
    parser.add_argument('internal_path', nargs='*',
            help="Path inside zipfile, relative to internal top-level."
            )

    # switches/options:
    parser.add_argument(
        '-a', '--all', action='store_true',
        help='do not ignore entries starting with .'
        )
    parser.add_argument(
        '--color', action='store_true',
        help='colorize the output'
        )
    parser.add_argument(
        '-F', '--classify', action='store_true',
        help='append indicator (one of */=>@) to entries'
        )
    parser.add_argument(
        '-l', action='store_true',
        help='use a long listing format'
        )
    #parser.add_argument(
    #    '-o', '--omit_hidden', action='store_true',
    #    help='Do not copy picasa hidden images to destination directory.')

    args = parser.parse_args(argv)

    return args


def ls_filter(zipinfolist, pathspec, args):
    return_paths = []
    no_such_file_dir = True

    for zipinfo in zipinfolist:
        if not args.all and zipinfo.filename.startswith("."):
            # omit all filenames starting with . unless -a or -all
            continue

        path = pathlib.Path(zipinfo.filename)

        # ls behavior types:
        #   1. pathspec is dir, and is identical to path
        #       -> append NOTHING, error=False
        #   2. pathspec is dir, path is child of pathspec
        #       -> append path relative to pathspec, error=False
        #   3. pathspec is dir, not a parent of path
        #       -> append NOTHING, error unchanged
        #   4. pathspec is dir, distant parent of path
        #       -> append NOTHING, error=False (or unchanged)
        #   5. pathspec is file, and is identical to path
        #       -> append path, error=False
        #   6. pathspec is file, and is not identical to path
        #       -> append NOTHING, error unchanged
        try:
            rel_path = path.relative_to(pathspec)
        except ValueError:
            # Types 3, 6
            continue

        if path == pathlib.Path(pathspec):
            if zipinfo.is_dir():
                # Type 1
                # append nothing
                pass
            else:
                # Type 5
                return_paths.append((str(path), zipinfo))
            no_such_file_dir = False
        elif rel_path.parent == pathlib.Path("."):
            # (We already know that it is not type 1)
            # Type 2
            return_paths.append((str(rel_path), zipinfo))
            no_such_file_dir = False

    if no_such_file_dir:
        # Error distinguishes from empty dir (returning empty return_paths)
        #   and non-existent path (raises error)
        raise(NoSuchFileDirError)

    return return_paths


def uncolored_len(in_str):
    return len(re.sub("\u001b"+r"\[[0-9;]+m", "", in_str))


def find_cols(str_list):
    """Find number of columns necessary to print list of strings

    Args:
        str_list (list of str): all strings to be output
    """
    longest_path = max([uncolored_len(x)+1 for x in str_list])
    numcols = max(int(TERM_COLS/longest_path), 1)
    return numcols


def print_cols(path_str_list):
    cols = find_cols(path_str_list)
    num_lines = math.ceil(len(path_str_list)/cols)
    col_width = int(TERM_COLS/cols)

    for line in range(num_lines):
        for col in range(cols):
            try:
                path = path_str_list[col*num_lines + line]
            except IndexError:
                # last line might not have all columns
                break
            print(path, end="")
            if col < cols-1:
                print(" "*(col_width-uncolored_len(path)), end="")
        print("")


def print_lines(path_str_list):
    for path_str in path_str_list:
        print(path_str)


def perm_octal2str(perm_octal):
    perm_str = ""

    # add to perm_str starting with LSB and working to MSB
    while len(perm_str) < 9:
        perm = perm_octal & 0o07
        perm_octal = perm_octal >> 3
        if perm & 1:
            perm_str = "x" + perm_str
        else:
            perm_str = "-" + perm_str
        if perm & 2:
            perm_str = "w" + perm_str
        else:
            perm_str = "-" + perm_str
        if perm & 4:
            perm_str = "r" + perm_str
        else:
            perm_str = "-" + perm_str

    return perm_str


def get_zip_perms(zipinfo):
    # TODO: only get permissions if they're valid (i.e. a unix-created zip?)
    perm_octal = (zipinfo.external_attr >> 16) & 0o0777
    return perm_octal


def get_zip_mtime(zipinfo):
    date = zipinfo.date_time
    datetm = datetime.datetime(date[0], date[1], date[2], date[3], date[4], date[5])
    if abs(datetm.now() - datetm) < datetime.timedelta(days=180):
        date_str = datetm.strftime("%b %m %H:%M ")
    else:
        date_str = datetm.strftime("%b %m  %Y ")

    return date_str


def color_classify(zip_path, args):
    color_on = ""
    color_off = ""
    classify_str = ""
    if zip_path[1].is_dir():
        if args.color:
            color_on = BLUE
            color_off = RESET
        if args.classify:
            classify_str = "/"
    elif get_zip_perms(zip_path[1]) & 0o100:
        if args.color:
            color_on = RED
            color_off = RESET
        if args.classify:
            classify_str = "*"

    return color_on + zip_path[0] + color_off + classify_str


def make_long_format(path_list, args):
    path_str_list = []
    color_on = ""
    color_off = ""
    classify_str = ""

    for path in path_list:
        #extra_data = path[1].extra
        #os_creator = path[1].create_system # 3-unix

        if path[1].is_dir():
            dir_str = "d"
        else:
            dir_str = "-"
        perm_octal = get_zip_perms(path[1])
        perm_str = perm_octal2str(perm_octal) + " "
        size_str = "%d "%path[1].file_size
        date_str = get_zip_mtime(path[1])
        path_str = color_classify(path, args)
        path_str_list.append(
                dir_str + perm_str + size_str + date_str + path_str
                )

    return path_str_list


def format_print_ls(path_list, args):
    if args.l:
        path_str_list = make_long_format(path_list, args)
    else:
        # short format
        path_str_list = [color_classify(x, args) for x in path_list]

    if not args.l:
        print_cols(path_str_list)
    else:
        print_lines(path_str_list)


def main(argv=None):
    args = process_command_line(argv)
    with zipfile.ZipFile(str(args.zipfile), 'r') as zip_fh:
        zipinfolist = zip_fh.infolist()

    internal_paths = args.internal_path or ['.']

    for pathspec in internal_paths:
        try:
            path_matches = ls_filter(zipinfolist, pathspec, args)
        except NoSuchFileDirError: 
            print("zipls: " + pathspec + ": No such file or directory in " + args.zipfile + ".")
        else:
            if len(internal_paths) > 1:
                print(pathspec + ":")
            format_print_ls(path_matches, args)
            if len(internal_paths) > 1:
                print("")

    return 0


if __name__ == "__main__":
    try:
        status = main(sys.argv)
    except KeyboardInterrupt:
        # Make a very clean exit (no debug info) if user breaks with Ctrl-C
        print("Stopped by Keyboard Interrupt", file=sys.stderr)
        # exit error code for Ctrl-C
        status = 130

    sys.exit(status)
