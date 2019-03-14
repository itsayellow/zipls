#!/usr/bin/env python3
"""
ls for inside of zipfile.
    some of the key ls switches from gnu ls are implemented
"""

# TODO: with -d option and no -l, all output strings should be put into columns
#       together
# TODO: make sure absolute paths in zip work as intended
# TODO: if zip file created (on Mac only?) with -jj (--absolute-path) all files
#   are stored without directory (all appear in top directory.)  Strange format

import argparse
import copy
import datetime
import math
import pathlib
import re
import shutil
import sys
import zipfile


TERM_COLS = shutil.get_terminal_size(fallback=(80, 24))[0]

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


class NoSuchFileDirError(Exception):
    """Custom error to indicate no such file or directory (differentiating
        from finding an empty directory with no contents)
    """
    pass


def process_command_line(argv):
    """Process command line invocation arguments and switches.

    Args:
        argv: list of arguments, or `None` from ``sys.argv[1:]``.

    Returns:
        argparse.Namespace: named attributes of arguments and switches
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
    parser.add_argument(
        '-d', '--directory', action='store_true',
        help='list directories themselves, not their contents'
        )
    parser.add_argument(
        '--hide_macosx', action='store_true',
        help='Hide Mac-specific top-level folder __MACOSX and descendants.' \
                ' (Not an ls option.)'
        )

    args = parser.parse_args(argv)

    return args


def ls_filter(zipinfolist, pathspec, args):
    """
    Args:
        zipinfolist (list of zipfile.Zipinfo): list of all Zipinfo obj.
            for all files inside of a zipfile
        pathspec (str): path to match against zipfile component files
        args (argparse.Namespace): user arguments to script, esp. switches

    Returns:
        list of tuples of (str, zipfile.Zipinfo): list the paths that match
            the specified pathspec
    """
    return_paths = []
    no_such_file_dir = True

    for zipinfo in zipinfolist:
        path = pathlib.Path(zipinfo.filename)

        # ls behavior types:
        #   1. pathspec is dir, and is identical to path
        #       -> a.) if -d append dirname, error=False
        #       -> b.) if not -d, append NOTHING, error=False
        #   2. pathspec is dir, path is child of pathspec
        #       -> a.) if -d, append NOTHING, error=False
        #       -> b.) if not -d, append path relative to pathspec, error=False
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

        if not args.all and re.search(r"^\..+", str(rel_path)):
            # omit all filenames starting with . unless -a or -all
            # (don't omit '.'!)
            continue

        if path == pathlib.Path(pathspec):
            if zipinfo.is_dir():
                if args.directory:
                    # Type 1a
                    return_paths.append((str(path), zipinfo))
                else:
                    # Type 1b
                    # append nothing
                    pass
            else:
                # Type 5
                return_paths.append((str(path), zipinfo))
            no_such_file_dir = False
        elif rel_path.parent == pathlib.Path("."):
            # (We already know that it is not type 1)
            if args.directory:
                # Type 2a
                pass
            else:
                # Type 2b
                return_paths.append((str(rel_path), zipinfo))
            no_such_file_dir = False

    if no_such_file_dir:
        # Error distinguishes from empty dir (returning empty return_paths)
        #   and non-existent path (raises error)
        raise NoSuchFileDirError

    return return_paths


def uncolored_len(in_str):
    """
    Args:
        in_str (str): string that may or may not have terminal coloring
            character sequences

    Returns:
        int: length of visible characters in in_str (not incl. color chars.)
    """
    return len(re.sub("\u001b"+r"\[[0-9;]+m", "", in_str))


def find_cols(str_list):
    """Find number of columns necessary to print list of strings

    Args:
        str_list (list of str): all strings to be output

    Returns:
        int: given lengths of items and width of current terminal,
            number of columns that would fit all str_list entries in each col.
    """
    if str_list:
        longest_path = max([uncolored_len(x)+1 for x in str_list])
        numcols = max(int(TERM_COLS/longest_path), 1)
    else:
        # empty str_list, just set one column as default
        numcols = 1

    return numcols


def print_cols(path_str_list):
    """
    Args:
        path_str_list (list of str): list of strings to print in columns
    """
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
    """
    Args:
        path_str_list (list of str): list of strings to print one per line
    """
    for path_str in path_str_list:
        print(path_str)


def perm_octal2str(perm_octal):
    """
    Args:
        perm_octal (int): octal-based file permissions specifier

    Returns:
        str: rwx--- type file permission string
    """
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
    """
    Args:
        zipinfo (zipfile.Zipinfo): information about one component file of a
            zip-file

    Returns:
        int: file permissions for file in octal
    """
    # TODO: only get permissions if they're valid (i.e. a unix-created zip?)
    perm_octal = (zipinfo.external_attr >> 16) & 0o0777
    return perm_octal


def get_zip_mtime(zipinfo):
    """
    Args:
        zipinfo (zipfile.Zipinfo): information about one component file of a
            zip-file

    Returns:
        str: date, "month day time" format if date is within 6 months past or
            future, "month day year" format otherwise.

    """
    # TODO: get more accurate mtime from other source than date_time in zipinfo
    date = zipinfo.date_time
    datetm = datetime.datetime(date[0], date[1], date[2], date[3], date[4], date[5])
    if abs(datetm.now() - datetm) < datetime.timedelta(days=180):
        date_str = datetm.strftime("%b %m %H:%M ")
    else:
        date_str = datetm.strftime("%b %m  %Y ")

    return date_str


def color_classify(zip_path, args):
    """
    Args:
        zip_path (tuple of (str, zipfile.Zipinfo)): relative file path in
            string and zipinfo object describing attributes
        args (argparse.Namespace): user arguments to script, esp. switches

    Returns:
        str: path string, colored if args.color, decorated with filetype
            ending character if args.classify
    """
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
    """
    Args:
        path_list (list of (str, zipfile.Zipinfo)): tuples, one per file
            component of zipfile, with relative file path and zipinfo
        args (argparse.Namespace): user arguments to script, esp. switches

    Returns:
        list of str: list of lines to be printed out one at a time
    """
    path_str_list = []

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
    """
    Args:
        path_list (list of (str, zipfile.Zipinfo)): tuples, one per file
            component of zipfile, with relative file path and zipinfo
        args (argparse.Namespace): user arguments to script, esp. switches
    """
    if args.l:
        path_str_list = make_long_format(path_list, args)
    else:
        # short format
        path_str_list = [color_classify(x, args) for x in path_list]

    if not args.l:
        print_cols(path_str_list)
    else:
        print_lines(path_str_list)


def glob_filter(internal_paths, zipinfolist):
    """implement a glob filter by hand

    glob seems to want to only want to look for real files in the system
        (not filter a list of strings)
    fnmatch seems to not want to respect / characters as different directories

    So we make our own.

    Args:
        internal_paths (list of str): list of paths to search for inside
            zip-file, which may or may not have glob-style wildcard characters
        zipinfolist (list of zipfile.Zipinfo): list of zipinfo objects, one
            for each file inside of zipfile

    Returns:
        list of str: list of input internal paths--paths with wildcard
            characters being replaced by a series of literal matching paths
    """
    glob_paths = []
    for pathspec in internal_paths:
        if '*' in pathspec or '?' in pathspec or re.search(r"\[.+\]", pathspec):
            # create escaped regexp
            pathspec_esc = "^" + re.escape(pathspec) + "$"
            # change \* to [^/]*
            pathspec_esc = re.sub(r"\\\*", r"[^/]*", pathspec_esc)
            # change \? to [^/]
            pathspec_esc = re.sub(r"\\\?", r"[^/]", pathspec_esc)
            # change \[\] to []
            pathspec_esc = re.sub(r"\\\[", r"[", pathspec_esc)
            pathspec_esc = re.sub(r"\\\]", r"]", pathspec_esc)

            pathspec_re = re.compile(pathspec_esc)

            glob_list = []
            for zipinfo in zipinfolist:
                if pathspec_re.search(zipinfo.filename.rstrip("/")):
                    glob_list.append(zipinfo.filename)
            if glob_list:
                glob_paths.extend(glob_list)
            else:
                # If doesn't match anything, add literal pathspec, which will
                #   also not match any actual file/dir, which will raise
                #   appropriate error.
                #   (If files had names with literal wildcard characters,
                #   they would match orig wildcard:
                #   e.g. file* would match file\*, file? would match file\? )
                glob_paths.append(pathspec)
        else:
            glob_paths.append(pathspec)

    return glob_paths


def get_zipinfo(zipfilename, args):
    """
    Args:
        zipfilename (str): name of zipfile to read and extract members from
        args (argparse.Namespace): user arguments to script, esp. switches

    Returns:
        list of zipfile.Zipinfo): list of zipinfo objects, one for each file
            inside of zipfile
    """
    try:
        with zipfile.ZipFile(str(zipfilename), 'r') as zip_fh:
            zipinfolist = zip_fh.infolist()
    except FileNotFoundError:
        print("No such zipfile: " + zipfilename)
        return 1
    except OSError:
        print("Cannot read zipfile: " + zipfilename)
        return 1

    # filter out toplevel folder __MACOSX and descendants if --hide_macosx
    #   Occurs when zip-file is created from macOS Finder
    #   (right click -> Compress <folder_name>)
    if args.hide_macosx:
        zipinfolist = [x for x in zipinfolist if not x.filename.startswith("__MACOSX/")]

    # If topmost dir is multiple levels deep, create "virtual" parent dirs in
    #   zipinfo list
    # Occurs when a zipfile is created with top-level dir more than one
    #   level deep.

    # find top-most directory internal to zip and its depth
    mindepth = 10000000 # infinity
    for zipinfo in zipinfolist:
        if zipinfo.is_dir():
            depth = zipinfo.filename.count("/")
            if depth < mindepth:
                zipinfo_mindepth = zipinfo
                mindepth = min(depth, mindepth)

    # create parent dirs for purposes of zipls if mindepth > 1
    new_zipinfo = zipinfo_mindepth
    while mindepth > 1:
        new_zipinfo = copy.copy(new_zipinfo)
        new_zipinfo.filename = str(pathlib.Path(new_zipinfo.filename).parent) + "/"
        zipinfolist.append(new_zipinfo)
        mindepth = mindepth - 1

    return zipinfolist


def main(argv=None):
    args = process_command_line(argv)

    # get list of all internal components in zipfile and attributes
    zipinfolist = get_zipinfo(args.zipfile, args)

    internal_paths = args.internal_path or ['.']
    glob_paths = glob_filter(internal_paths, zipinfolist)

    first_item = True
    for pathspec in glob_paths:
        try:
            path_matches = ls_filter(zipinfolist, pathspec, args)
        except NoSuchFileDirError:
            print("zipls: " + pathspec + ": No such file or directory in " + args.zipfile + ".")
        else:
            if (len(glob_paths) > 1) and not args.directory and not first_item:
                print("")
            if (len(glob_paths) > 1) and not args.directory:
                # print pathspec: if more than one glob_path and no -d switch
                if not (path_matches[0][0]==pathspec and not path_matches[0][1].is_dir()):
                    # don't print pathspec: if pathspec identical to path_match
                    #   and path_match is file
                    print(pathspec.rstrip("/") + ":")
            format_print_ls(path_matches, args)
            first_item = False

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
