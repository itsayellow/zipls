#!/usr/bin/env python3
"""
ls for inside of zipfile.
    some of the key ls switches from gnu ls are implemented
"""

# TODO: make sure absolute paths in zip work as intended
# TODO: if zip file created (on Mac only?) with -jj (--absolute-path) all files
#   are stored without directory (all appear in top directory.)  Strange format

import argparse
import datetime
import math
import re
import shutil
import sys
import time
import zipfile

#import anytree


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
    parser = argparse.ArgumentParser(description="ls inside of a zipfile.")

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


def uncolored_len(in_str):
    """Return len of str, ignoring any terminal color sequences
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
    """Output all strings in list in as narrow of columns as possible

    Sequence proceeds down column 0, then col. 1, etc.

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
    """Take strings in list, output one per line
    Args:
        path_str_list (list of str): list of strings to print one per line
    """
    for path_str in path_str_list:
        print(path_str)


def perm_octal2str(perm_octal):
    """Convert octal permission int to permission string
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
    """Get file/dir permissions from zipinfo
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
    """Get file/dir modification time from zipinfo
    Args:
        zipinfo (zipfile.Zipinfo): information about one component file of a
            zip-file

    Returns:
        str: date, "month day time" format if date is within 6 months past or
            future, "month day year" format otherwise.

    """
    # TODO: some mtimes seem to differ for directories, extracted ls vs. zipls
    date = zipinfo.date_time
    datetm = datetime.datetime(date[0], date[1], date[2], date[3], date[4], date[5])
    if abs(datetm.now() - datetm) < datetime.timedelta(days=180):
        date_str = "{d:%b} {d.day:>2} {d:%H}:{d:%M} ".format(d=datetm)
    else:
        date_str = "{d:%b} {d.day:>2}  {d.year} ".format(d=datetm)

    return date_str


def color_classify(zip_path, args):
    """For given path, deocrate with possible color, ending char based on type
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
    """Output list of strings in informative line-by-line format like ls -l
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
    """Print path_list result of ls operation according to args switches
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


def glob_to_re(glob_str):
    """Convert glob str to compiled regexp object
    """
    glob_str_esc = "^" + re.escape(glob_str) + "$"
    if '*' in glob_str or '?' in glob_str or re.search(r"\[.+\]", glob_str):
        # create escaped regexp
        # change \* to [^/]*
        glob_str_esc = re.sub(r"\\\*", r"[^/]*", glob_str_esc)
        # change \? to [^/]
        glob_str_esc = re.sub(r"\\\?", r"[^/]", glob_str_esc)
        # change \[\] to []
        glob_str_esc = re.sub(r"\\\[", r"[", glob_str_esc)
        glob_str_esc = re.sub(r"\\\]", r"]", glob_str_esc)

    glob_re = re.compile(glob_str_esc)
    return glob_re


def path_join(path_parts):
    """Join path parts with /, also ignore any parts that are ""

    Args:
        path_parts (list of str): each part of list is another dir in
            path

    Returns:
        str: pathname with / separators, relative path, ignoring "" path parts
    """
    return "/".join([x for x in path_parts if x != ""])


def ls_filter(zipinfo_dict, pathspec, args):
    """Return all paths matching pathspec from zipinfo_dict

    Include children of pathspec dir if not -d option

    Args:
        zipinfo_dict (dict of FileDirNode): dict of all FileDir obj.
            for all files inside of a zipfile
        pathspec (str): path to match against zipfile component files
        args (argparse.Namespace): user arguments to script, esp. switches

    Returns:
        list of tuples of (str, zipfile.Zipinfo): list the paths that match
            the specified pathspec
    """
    return_paths = []

    try:
        children = zipinfo_dict[pathspec].children
    except KeyError:
        raise NoSuchFileDirError

    if children is not None and not args.directory:
        # pathspec is directory
        # return relative paths of children of pathspec dir
        return_paths = []
        for child in children:
            if not child.startswith('.') or args.all:
                child_path = path_join((pathspec, child))
                return_paths.append((child, zipinfo_dict[child_path].zipinfo))
    else:
        # pathspec is file OR pathspec is dir, but args.directory is set
        # return pathspec itself and its own zipinfo
        return_paths = [(pathspec, zipinfo_dict[pathspec].zipinfo)]

    return return_paths


def glob_recurse(path, zipinfo_dict, output_paths):
    """Recursive search for all zipinfo_dict that match path
    Args:
        path (str): path with glob wildcards to match in zipinfo_dict
        zipinfo_dict (dict of FileDirNode): dict of all FileDir obj.
            for all files inside of a zipfile
        output_paths (list of str): matching paths are appended to this
            as they are found (start with empty path if starting recursion)
    """
    path_dirs = path.split("/")
    first_glob = 0
    for (i, path_dir) in enumerate(path_dirs):
        if '*' in path_dir or '?' in path_dir or re.search(r"\[.+\]", path_dir):
            break
        first_glob = i+1
    parent = path_join(path_dirs[0:first_glob])
    try:
        mid_level = path_dirs[first_glob]
    except IndexError:
        mid_level = None
    tail = path_join(path_dirs[first_glob+1:])

    if parent in zipinfo_dict:
        if mid_level is None:
            output_paths.append(parent)
        else:
            if zipinfo_dict[parent].children is not None:
                # find all matches for mid_level
                glob_re = glob_to_re(mid_level)
                mid_matches = [
                        x for x in zipinfo_dict[parent].children.keys()
                        if glob_re.search(x)
                        ]
                for mid_match in mid_matches:
                    recurse_dir = path_join((parent, mid_match, tail))
                    glob_recurse(recurse_dir, zipinfo_dict, output_paths)


def glob_filter(internal_paths, zipinfo_dict):
    """implement a glob filter by hand

    python glob seems to want to only want to look for real files in the system
        (not filter a list of strings)
    python fnmatch seems to not want to respect / characters as different
        directories

    So we make our own.

    Args:
        internal_paths (list of str): list of paths to search for inside
            zip-file, which may or may not have glob-style wildcard characters
        zipinfo_dict (dict of FileDirNode): dict of all FileDir obj.
            for all files inside of a zipfile

    Returns:
        list of str: list of input internal paths--paths with wildcard
            characters being replaced by a series of literal matching paths
    """
    output_paths = []
    for pathspec in internal_paths:
        # normalize pathspec by discarding any possible trailing /
        pathspec = pathspec.rstrip("/")
        glob_paths = []
        glob_recurse(pathspec, zipinfo_dict, glob_paths)
        if glob_paths:
            output_paths.extend(glob_paths)
        else:
            # if we found nothing, add literal glob path (with wildcard chars)
            #   so that it shows up as not found in future ls_filter call
            output_paths.append(pathspec)

    return output_paths


class FileDirNode:
    """For clarity, encapsulates zipinfo and children if dir.

    Could have been a list or dict, is class for code readability.
    Is maybe tiny bit slower creation than a list or dict.
    """
    def __init__(self, zipinfo=None, children=None):
        self.zipinfo = zipinfo
        self.children = children


def create_node_and_ancestors(node_name, zipinfo, zipinfo_dict):
    """
    node_name doesn't exist, create it and all necessary ancestors back to
    root node ""

    Args:
        node_name (str): node to be created (and ancestors if necessary)
        zipinfo (zipfile.Zipinfo): zipinfo to attach to all created nodes
        zipinfo_dict (dict of FileDirNode): dict of all FileDir obj.
            for all files inside of a zipfile
    """
    node_components = ["",] + node_name.split("/")
    for (i, _) in enumerate(node_components):
        me = path_join(node_components[:i+1])
        my_parent = path_join(node_components[:i])
        my_leaf = node_components[i]
        try:
            zipinfo_dict[me]
        except KeyError:
            # no node named me
            # highest unspecified node currently
            zipinfo_dict[my_parent].children[my_leaf] = FileDirNode(zipinfo=zipinfo, children={})
            zipinfo_dict[me] = zipinfo_dict[my_parent].children[my_leaf]


def get_zipinfo(zipfilename, args):
    """
    Putting the archive internal files into a dict and tree costs ~8% more
    time here, but makes searching for paths later almost instantaneous.
    (i.e. overall script speedup of ~5x with one pathspec, more if multiple
    pathspecs)

    Args:
        zipfilename (str): name of zipfile to read and extract members from
        args (argparse.Namespace): user arguments to script, esp. switches

    Returns:
        dict of FileDirNode: dict of FildDirNode objects, one for each file
            inside of zipfile
    """
    with zipfile.ZipFile(str(zipfilename), 'r') as zip_fh:
        zipinfolist = zip_fh.infolist()

    # tree root
    zipinfo_dict = {"":FileDirNode(zipinfo=None, children={})}

    for zipinfo in zipinfolist:
        # filter out toplevel folder __MACOSX and descendants if --hide_macosx
        #   Occurs when zip-file is created from macOS Finder
        #   (right click -> Compress <folder_name>)
        if args.hide_macosx and zipinfo.filename.startswith("__MACOSX/"):
            continue

        this_filedir = zipinfo.filename.rstrip("/")
        (parent_name, _, leaf_name) = this_filedir.rpartition("/")
        try:
            node_parent = zipinfo_dict[parent_name]
        except KeyError:
            # no node parent_name already in FileDirNode and zipinfo_dict,
            #   create it and all necessary ancestors
            create_node_and_ancestors(parent_name, zipinfo, zipinfo_dict)
            node_parent = zipinfo_dict[parent_name]

        if zipinfo.is_dir():
            # Paranoia: check that children[leaf_name] doesn't already exist?
            #   e.g. we found a lower child directory in the archive first
            #       before this one
            if leaf_name not in node_parent.children:
                node_parent.children[leaf_name] = FileDirNode(zipinfo=zipinfo, children={})
            else:
                # I don't think this should happen, but it might
                #print("INTERNAL: dir already exists")
                node_parent.children[leaf_name].zipinfo = zipinfo
        else:
            node_parent.children[leaf_name] = FileDirNode(zipinfo=zipinfo, children=None)

        zipinfo_dict[this_filedir] = node_parent.children[leaf_name]

    return zipinfo_dict


def main(argv=None):
    args = process_command_line(argv)

    # get list of all internal components in zipfile and attributes
    try:
        zipinfo_dict = get_zipinfo(args.zipfile, args)
    except FileNotFoundError:
        print("No such zipfile: " + args.zipfile)
        return 1
    except OSError:
        print("Cannot read zipfile: " + args.zipfile)
        return 1

    # if no paths specified, use '' for root path
    internal_paths = args.internal_path or ['']

    # convert paths with wildcard paths to one or more actual paths
    glob_paths = glob_filter(internal_paths, zipinfo_dict)

    # get all types of results from paths
    no_such_paths = []
    file_paths = []
    dir_paths = []
    for pathspec in glob_paths:
        try:
            path_matches = ls_filter(zipinfo_dict, pathspec, args)
        except NoSuchFileDirError:
            no_such_paths.append(pathspec)
        else:
            if len(path_matches) == 1 and path_matches[0][0] == pathspec:
                # handles regular files matching pathspec AND handles dirs
                #   matching pathspec if -d switch on
                file_paths.extend(path_matches)
            else:
                dir_paths.append([pathspec, path_matches])

    # print results
    previous_printing = False
    for no_such_path in no_such_paths:
        print("zipls: " + no_such_path + ": No such file or directory in " + args.zipfile + ".")
        previous_printing = True
    if file_paths:
        format_print_ls(sorted(file_paths), args)
        previous_printing = True
    for dir_path in sorted(dir_paths, key=lambda x: x[0]):
        if previous_printing:
            print("")
        if previous_printing or len(dir_paths) > 1:
            print(dir_path[0] + ":")
        format_print_ls(sorted(dir_path[1]), args)
        previous_printing = True

    return 0


if __name__ == "__main__":
    try:
        #start_time = time.time()
        status = main(sys.argv)
        #el_time = time.time() - start_time
        #print("Elapsed time: %.3f seconds"%el_time)
    except KeyboardInterrupt:
        # Make a very clean exit (no debug info) if user breaks with Ctrl-C
        print("Stopped by Keyboard Interrupt", file=sys.stderr)
        # exit error code for Ctrl-C
        status = 130

    sys.exit(status)
