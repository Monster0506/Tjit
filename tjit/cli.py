import argparse
import os
import subprocess
import sys
import shutil
import textwrap


from . import base
from . import data
from . import diff
from . import remote


def main():
    with data.change_git_dir("."):
        args = parse_args()
        args.func(args)


def parse_args():
    parser = argparse.ArgumentParser()

    commands = parser.add_subparsers(dest="command")
    commands.required = True

    oid = base.get_oid

    k_parser = commands.add_parser("k")
    k_parser.set_defaults(func=k)

    parser.add_argument("--version", "-v", action="version", version="%(prog)s 1.0.0")
    #  vparser = commands.add_parser('--version','-v', action='version', version='%(prog)s 1.0.0')
    #  parser.add_argument('-v', action='version', version='%(prog)s 1.0')

    destroy_parser = commands.add_parser(
        "destroy",
        help="tjit init' is the command to initalize a repository. It creates a .tjit directory'",
    )
    destroy_parser.set_defaults(func=destroy)
    destroy_parser.add_argument("y")

    help_parser = commands.add_parser("help")
    help_parser.set_defaults(func=helpMe)
    help_parser.add_argument("-i")

    init_parser = commands.add_parser("init")
    init_parser.set_defaults(func=init)
    init_parser.add_argument("--destroy")

    hash_object_parser = commands.add_parser("hash-object")
    hash_object_parser.set_defaults(func=hash_object)
    hash_object_parser.add_argument("file")

    cat_file_parser = commands.add_parser("cat-file")
    cat_file_parser.set_defaults(func=cat_file)
    cat_file_parser.add_argument("object", type=oid)

    write_tree_parser = commands.add_parser("write-tree")
    write_tree_parser.set_defaults(func=write_tree)

    read_tree_parser = commands.add_parser("read-tree")
    read_tree_parser.set_defaults(func=read_tree)
    read_tree_parser.add_argument("tree", type=oid)

    commit_parser = commands.add_parser("commit")
    commit_parser.set_defaults(func=commit)
    commit_parser.add_argument("-m", "--message", required=True)

    log_parser = commands.add_parser("log")
    log_parser.set_defaults(func=log)
    log_parser.add_argument("oid", default="@", type=oid, nargs="?")

    show_parser = commands.add_parser("show")
    show_parser.set_defaults(func=show)
    show_parser.add_argument("oid", default="@", type=oid, nargs="?")

    diff_parser = commands.add_parser("diff")
    diff_parser.set_defaults(func=_diff)
    diff_parser.add_argument("--cached", action="store_true")
    diff_parser.add_argument("commit", nargs="?")

    checkout_parser = commands.add_parser("checkout")
    checkout_parser.set_defaults(func=checkout)
    checkout_parser.add_argument("commit")

    tag_parser = commands.add_parser("tag")
    tag_parser.set_defaults(func=tag)
    tag_parser.add_argument("name")
    tag_parser.add_argument("oid", default="@", type=oid, nargs="?")

    branch_parser = commands.add_parser("branch")
    branch_parser.set_defaults(func=branch)
    branch_parser.add_argument("name", nargs="?")
    branch_parser.add_argument("start_point", default="@", type=oid, nargs="?")

    status_parser = commands.add_parser("status")
    status_parser.set_defaults(func=status)

    reset_parser = commands.add_parser("reset")
    reset_parser.set_defaults(func=reset)
    reset_parser.add_argument("commit", type=oid)

    merge_parser = commands.add_parser("merge")
    merge_parser.set_defaults(func=merge)
    merge_parser.add_argument("commit", type=oid)

    merge_base_parser = commands.add_parser("merge-base")
    merge_base_parser.set_defaults(func=merge_base)
    merge_base_parser.add_argument("commit1", type=oid)
    merge_base_parser.add_argument("commit2", type=oid)

    fetch1_parser = commands.add_parser("pull")
    fetch1_parser.set_defaults(func=fetch)
    fetch1_parser.add_argument("remote")
    fetch_parser = commands.add_parser("fetch")
    fetch_parser.set_defaults(func=fetch)
    fetch_parser.add_argument("remote")

    push_parser = commands.add_parser("push")
    push_parser.set_defaults(func=push)
    push_parser.add_argument("remote")
    push_parser.add_argument("branch")

    add_parser = commands.add_parser("add")
    add_parser.set_defaults(func=add)
    add_parser.add_argument("files", nargs="+")

    return parser.parse_args()


def init(args):
    if args.destroy:
        destroy(args)
        return
    base.init()
    print(f"Initialized empty tjit repository in {os.getcwd()}/{data.GIT_DIR}")


def hash_object(args):
    with open(args.file, "rb") as f:
        print(data.hash_object(f.read()))


def destroy(args):
    shutil.rmtree(data.GIT_DIR)
    if os.path.isfile(".tjitignore"):
        os.remove(".tjitignore")


def cat_file(args):
    sys.stdout.flush()
    sys.stdout.buffer.write(data.get_object(args.object, expected=None))


def write_tree(args):
    print(base.write_tree())


def read_tree(args):
    base.read_tree(args.tree)


def commit(args):
    print(base.commit(args.message))


def _print_commit(oid, commit, refs=None):
    refs_str = f'({", ".join(refs)})' if refs else ""
    print(f"commit {oid}{refs_str}\n\n")
    print(textwrap.indent(commit.message, "    "))
    print("")


def log(args):
    refs = {}
    for refname, ref in data.iter_refs():
        refs.setdefault(ref.value, []).append(refname)

    for oid in base.iter_commits_and_parents({args.oid}):
        commit = base.get_commit(oid)
        _print_commit(oid, commit, refs.get(oid))


def show(args):
    if not args.oid:
        return
    commit = base.get_commit(args.oid)
    parent_tree = None
    if commit.parents:
        parent_tree = base.get_commit(commit.parents[0]).tree

    _print_commit(args.oid, commit)
    result = diff.diff_trees(base.get_tree(parent_tree), base.get_tree(commit.tree))
    sys.stdout.flush()
    sys.stdout.buffer.write(result)


def _diff(args):
    oid = args.commit and base.get_oid(args.commit)

    if args.commit:
        # If a commit was provided explicitly, diff from it
        tree_from = base.get_tree(oid and base.get_commit(oid).tree)

    if args.cached:
        tree_to = base.get_index_tree()
        if not args.commit:
            # If no commit was provided, diff from HEAD
            oid = base.get_oid("@")
            tree_from = base.get_tree(oid and base.get_commit(oid).tree)
    else:
        tree_to = base.get_working_tree()
        if not args.commit:
            # If no commit was provided, diff from index
            tree_from = base.get_index_tree()

    result = diff.diff_trees(tree_from, tree_to)
    sys.stdout.flush()
    sys.stdout.buffer.write(result)


def checkout(args):
    base.checkout(args.commit)


def tag(args):
    base.create_tag(args.name, args.oid)


def branch(args):
    if not args.name:
        current = base.get_branch_name()
        for branch in base.iter_branch_names():
            prefix = "*" if branch == current else " "
            print(f"{prefix} {branch}")
    else:
        base.create_branch(args.name, args.start_point)
        print(f"Branch {args.name} created at {args.start_point[:10]}")


def status(args):
    HEAD = base.get_oid("@")
    branch = base.get_branch_name()
    if branch:
        print(f"On branch {branch}")
    else:
        print(f"HEAD detached at {HEAD[:10]}")

    MERGE_HEAD = data.get_ref("MERGE_HEAD").value
    if MERGE_HEAD:
        print(f"Merging with {MERGE_HEAD[:10]}")

    print("\n\nChanges to be committed:\n")
    HEAD_tree = HEAD and base.get_commit(HEAD).tree
    for path, action in diff.iter_changed_files(
        base.get_tree(HEAD_tree), base.get_index_tree()
    ):
        print(f"{action:>12}: {path}")

    print("\n\nChanges not staged for commit:\n")
    for path, action in diff.iter_changed_files(
        base.get_index_tree(), base.get_working_tree()
    ):
        print(f"{action:>12}: {path}")


def reset(args):
    base.reset(args.commit)


def merge(args):
    base.merge(args.commit)


def merge_base(args):
    print(base.get_merge_base(args.commit1, args.commit2))


def fetch(args):
    remote.fetch(args.remote)


def push(args):
    remote.push(args.remote, f"refs/heads/{args.branch}")


def k(args):
    dot = "digraph commits {\n"

    oids = set()
    for refname, ref in data.iter_refs(deref=False):
        dot += f'"{refname}" [shape=note]\n'
        dot += f'"{refname}" -> "{ref.value}"\n'
        if not ref.symbolic:
            oids.add(ref.value)

    for oid in base.iter_commits_and_parents(oids):
        commit = base.get_commit(oid)
        dot += f'"{oid}" [shape=box style=filled label="{oid[:10]}"]\n'
        for parent in commit.parents:
            dot += f'"{oid}" -> "{parent}"\n'

    dot += "}"
    print(dot)

    with subprocess.Popen(
        ["dot", "-Tx11", "/dev/stdin"], stdin=subprocess.PIPE
    ) as proc:
        proc.communicate(dot.encode())


def add(args):
    base.add(args.files)


def helpMe(args):
    print(args.i)
    if args.i:
        argument = args.i.lower()
        if argument == "init":
            print(
                "'tjit init' is the command to initalize a repository. It creates a .tjit directory"
            )
        if argument == "add":
            print("'tjit add <FILES>'. Add a file to the index.")
        if argument == "commit":
            print(
                "'tjit commit -m <MESSAGE>'. Commits a file to the head. Returns the hash of the object."
            )
        if argument == "status":
            print("'tjit status'. Print the status of the current branch.")
        if argument == "log":
            print("'tjit log [OID or TAG]' Prints information about the object.")
        if argument == "show":
            print(
                "'tjit show [OID or TAG]'. Prints a difference in the object from the head."
            )
        if argument == "cat_file":
            print(
                "'tjit cat-file [OID or TAG]'. Prints some information about an object."
            )
        if argument == "help":
            print(
                "'tjit help [-i <COMMAND>]'. Print some information about tjit or a specific command"
            )
        if argument == "tag":
            print(
                "`tags` can be two things. In the terms of 'tjit tag', please see 'tjit help -i nametag'\nIn terms of the object, please see 'tjit help -i tags'"
            )
        if argument == "nametag":
            print(
                "'tjit tag <NAME> [OID or TAG]'. If a tag is not provided, defaults to head. Creates an easier reference to an object. Can be called in checkout, commit, etc."
            )
        if argument == "tags":
            print(
                "A tag is a reference point to an object in string format. This can be used instead of an OID. A builtin tag is '@', which defaults to HEAD"
            )
        if argument in ["fetch", "pull"]:
            print(
                f"'tjit {args.i} <PATH/TO/REPOSITORY>'. Creates a new object containing information from a remote repository."
            )
        if argument == "push":
            print(
                "'tjit push <PATH/TO/REPOSITORY>'. Used to move changes to a remote repository."
            )
        if argument == "branch":
            print(
                "'tjit branch <BRANCHNAME>'. Creates a new branch and returns the hash."
            )
        if argument == "checkout":
            print(
                "'tjit checkout <BRANCHNAME>'. Moves the working index to that branch."
            )
        if argument == "destroy":
            print(
                "'tjit destroy y' or 'tjit init --destroy'. Deletes the tjit folder and .tjitignore files completely. USE AT YOUR OWN RISK"
            )
        if argument == "merge":
            print("'tjit merge <BRANCHNAME>'. Merge a branch to the the current.")
        if argument == "merge-base":
            print("'tjit merge-base <OID or TAG> <OID or TAG>'. Merge two commits.")
        if argument == "read-tree":
            print("'tjit read-tree <OID or TAG>'. Display information about a tree.")
        if argument == "write-tree":
            print("tjit ")
    else:
        print(
            'First, run "tjit init" in the directory that you want to create as a tjit repository.\nThen, run  "tjit add ."(Don\'t forget the dot!) to add all files to the index.\n\
You can run "tjit status" to view the staged and ready-to-be committed files.\nEverytime that you make changes, run the "tjit add <FILES>" command to add these files to the index\
Next, when changes are complete, you can run the "tjit commit -m <MESSAGE> command. The message is mandatory. This saves your changes, and gives you a hash to look at and save.\n\
You can run "tjit log" to view the commits and their messages.\nYou can also run "tjit show <HASH>" to view changes between objects.\nYou can also run the "tjit reset <HASH>" command to \
revert back to an earlier commit.\nThe "tjit branch <BRANCHNAME>" command will create a new branch that you can use. The "tjit checkout <BRANCHNAME>" will switch into that branch.\n\
You can use "tjit cat-file <HASH>" to view some useful information about an object.\n"tjit merge" and "tjit merge-base" will merge branches.\n"tjit write-tree" will create a tree object, \
which you can view with "read-tree" or "cat-file.\nTo completely remove a repository(locally), run either "tjit destroy y" or "tjit init --destroy". USE AT YOUR OWN RISK\n\
You can fetch or pull from a remote repository with either "tjit fetch <REMOTE>" or "tjit pull <REMOTE>". You can push to a repository with the command "tjit push <REMOTE>"\nFinally, you \
can tag a commit with the "tjit tag <TAGNAME> [COMMIT HASH]" command, for easier checkout.'
        )
        print("To recieve specific help on a command, run 'tjit help -i <COMMAND>'")
