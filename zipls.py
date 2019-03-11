#!/usr/bin/env python3
#
# ls for inside of zipfile

# TODO: handle globbing, wildcards, e.g. * ?
# TODO: terminal coloring
# TODO: zipls -l

import argparse
import pathlib
import shutil
import sys
import zipfile


TERM_COLS = shutil.get_terminal_size(fallback=(80,24))[0]


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
    #parser.add_argument(
    #    '-s', '--max_size', action='store',
    #    help='String specifying maximum size of images.  ' \
    #            'Larger images will be resized. (e.g. "1024x768")')
    #parser.add_argument(
    #    '-o', '--omit_hidden', action='store_true',
    #    help='Do not copy picasa hidden images to destination directory.')

    args = parser.parse_args(argv)

    return args


def lslist(zipinfolist, pathspec):
    return_paths = []
    no_such_file_dir = True

    for zipinfo in zipinfolist:
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
                return_paths.append(str(path))
            no_such_file_dir = False
        elif rel_path.parent == pathlib.Path("."):
            # (We already know that it is not type 1)
            # Type 2
            if zipinfo.is_dir():
                return_paths.append(str(rel_path) + "/")
            else:
                return_paths.append(str(rel_path))
            no_such_file_dir = False

    if no_such_file_dir:
        # Error distinguishes from empty dir (returning empty return_paths)
        #   and non-existent path (raises error)
        raise(NoSuchFileDirError)

    return return_paths


def find_cols(paths):
    longest_path = max([len(x)+1 for x in paths])
    numcols = int(TERM_COLS/longest_path)
    # TODO: is there a problem with to int( / ) here?
    return numcols


def format_print_ls(paths):
    cols = find_cols(paths)
    col_width = int(TERM_COLS/cols)
    column = 0
    for path in paths:
        print(path, end="")
        print(" "*(col_width-len(path)), end="")
        column += 1
        if column == cols:
            column = 0
            print("")
    print("")


def main(argv=None):
    args = process_command_line(argv)
    with zipfile.ZipFile(str(args.zipfile), 'r') as zip_fh:
        zipinfolist = zip_fh.infolist()

    internal_paths = args.internal_path or ['.']

    for pathspec in internal_paths:
        try:
            path_matches = lslist(zipinfolist, pathspec)
        except NoSuchFileDirError: 
            print("zipls: " + pathspec + ": No such file or directory in " + args.zipfile + ".")
        else:
            if len(internal_paths) > 1:
                print(pathspec + ":")
            format_print_ls(path_matches)
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
