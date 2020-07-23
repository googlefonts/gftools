# `gftools packager`

Tool to take files from a font family project upstream git repository to the [google/fonts GitHub](https://github.com/google/fonts) repository structure, taking care of all the details.

    usage: gftools packager [-h] [-f] [-y] [-q] [-g] [-b BRANCH] [-a] [-p] [--pr-upstream PR_UPSTREAM] [--push-upstream PUSH_UPSTREAM] [--no-whitelist] [name [name ...]] target

Show the command line help:

    $ gftools packager -h

## Environment Variables

* `GH_TOKEN` **mandatory** used to access the GitHub GraphQL API to get info about the font family in the google/fonts repo and to download the current versions of the package.
* `VISUAL` and `EDITOR` **optional** The command to open a text editor in order to create or edit an `upstream.yaml` file. If `VISUAL` is set it will be used, otherwise `EDITOR`, if set, will be used. The default/fallback editor command is `vi`, (which in many cases will open vim). This is similar to the way the `git` command decides which editor to use.

This is how to set environment variables:

    $ export GH_TOKEN=mypersonalgithubapitoken
    $ export VISUAL=gedit

You can also put these commands into a file:

    # file: set_local_env
    export GH_TOKEN=mypersonalgithubapitoken
    export VISUAL=gedit

Then run:

    $ source set_local_env

Or put the commands into your `~/.bashrc` and the variables will be set for each newly started bash terminal.

## `upstream.yaml` Upstream Configuration

The tool introduces and relies on "upstream configuration" in the form of an `upstream.yaml` file, located in the family directory on google/fonts. Initially for each update to a family or newly added family an `upstream.yaml` file will have to be created. The packager supports this by providing a template, with documenting comments, that it opens in an interactive text editor.

You should have a look at the [`upstream.yaml` template](../../Lib/gftools/template.upstream.yaml) now to make yourself familiar.

An `upstream.yaml` file path can also be used as a `name` argument from the command line. Eventually, when the `upstream.yaml` already exists in the family directory of google/fonts, and no modification to it is required, an update and Pull Request (PR) of the family can be done in one call to the packager.

## `name` Family Name or `upstream.yaml` File Name

The tool takes zero or more family names or file names and creates a package (and commit) for each.

If a `name` ends with `.yaml` or `.yml` it is treated as a file path to an `upstream.yaml` configuration file. Otherwise it's treated as a family name that will be searched in google/fonts for existing `upstream.yaml` configuration. The family entry will be updated if found or created otherwise. The family name in this case can be:

* the full family name like `"Family Sans"` (use quotes or escapes on the command line if it contains spaces),
* the camel cased name `FamilySans` or
* the all lowercase directory name `familysans`.

To search the family on google fonts, the name will be made all lower case and spaces will be removed.
In the full name case, if the family is not on google fonts, the suggestion in the `upstream.yaml` editor template will already be set correctly.

## `target` Directory or Git Repository

The target argument can be either treated as a directory or as a git repository (use `-g/--gf-git`) that is a clone of google/fonts.

### Directory (*default*)

If `target` is treated as a directory, the tool will simply add the files package into its `{license_dir}/{family_dir}` directory within `target`. Note that in this case `target` can also be the current working tree of a git repository, but it can also be an empty or any other directory. If the sub-directory `{license_dir}/{family_dir}` already exists, it can't be overridden without giving explicit permission (`-f/--force` or answering in interactive mode).

This is useful for a local quality assurance (QA) development-feedback loop when mastering a family for google/fonts. See `gftools qa` for this. Especially Font Bakery with the `googlefonts` profile (i.e. `fontbakery check-googlefonts`) is set up to check all the contents of the family package, not just the font files, and has ideally also access to the google/fonts directory structure and possible sibling families. Thus, putting the package into a checked out working directory of google/fonts master is the optimal case for local QA.

### Git Repository `-g/--gh-git`

To use `target` as a google/fonts git repository it must have a git remote that can fetch from google/fonts, e.g. with the url `git@github.com:google/fonts.git` or `https://github.com/google/fonts.git`.

**NOTE:** command line flags and arguments that **imply** that target is a git repository *will also **implicitly set** the `-g/--gh-git` flag*. Such are `-b/--branch`, `-a/--ad-commit`, `-p/--pr` and—by implying `-p/--pr`—`--pr-upstream` and `--push-upstream`.

In this mode the tool will create a new git branch or add to an existing one (with `-a/--add-commit`). Use `-b/--branch` to explicitly specify a branch or the tool will create a branch name based on the given actual family names and the prefix `gftools_packager_`. An existing branch, when creating a new branch, can't be overridden without giving explicit permission (`-f/--force` or answering in interactive mode).

*A limitation here is:* If the branch is checked out, in the current working directory of the repository, it won't be possible to override it or add commits to it!

To push the branch to the remote and make a PR to `https://github.com/google/fonts` with the package(s) use the `-p/--pr` flag. Note that the remote branch will always be prefixed with `gftools_packager_` even if the local branch (when using `-b/--branch`) is not prefixed by that. This is because the push to the remote branch **will always be a `git push --force`** no matter if (`-f/--force`) was used or not. That way we ensure that only remote branches that were (likely) created by the tool are overridden by the tool, not accidentally other branches. An existing PR for the same branch name will simply be updated and a status comment will be added to the PR discussion.

Interesting arguments, together with `-p/--pr`, to push and/or PR to other GitHub repositories are `--pr-upstream` and `--push-upstream`. These are so far mainly used for development/debugging/testing in order to reduce noise on the google/fonts repository. However, in some cases `--push-upstream` can be used to push to a fork of google/fonts and then let the tool make a PR to google/fonts, e.g. when the user has no `WRITE` permission for google/fonts. But, currently, the continuous integration QA tools that check the PR can't handle branches on repositories other than google/fonts, so the utility of this is lower.

## Interactive Mode

Interactive mode is the default mode of the tool. To turn it off use the `-y/--no-confirm` flag and the tool will never ask for user interaction. This is especially useful for automation purposes, then together with the `-f/--force` flag, or when everything is expected to be set up correctly and the tool should just do its thing.

## Use Cases and Workflows

There are multiple use cases for this tool.

### Create or Update a Font Family on google/fonts:

If the family already has an `upstream.yaml` file in its google/fonts directory, this will do (`-p/--pr`: make a PR, implying `-g/--gf-git`):

    $ gftools packager "Family Serif" path/to/google/fonts/clone -p
    # or
    $ gftools packager "Family Serif" path/to/google/fonts/clone --pr

It will however ask if want to to edit the `upstream.yaml` file or not. If answered positively, an editor will be opened with the contents of the file.

In the case of a family that is not on google/fonts or not yet has an `upstream.yaml` file on google/fonts, the tool will help tyou interactively to create such a file.

In case the `upstream.yaml` is up to date, the `-y/--no-confirm` flag will prevent any user interaction and result in an uninterrupted program flow, but that can also lead to an early exit of the program:

    $ gftools packager "Family Serif" path/to/google/fonts/clone -p -y
    # or
    $ gftools packager "Family Serif" path/to/google/fonts/clone --pr --no-confirm

The git branch created in this example will be called `gftools_packager_familyserif` and if it already exists, e.g. from a previous attempt, the tool can't override the branch without explicit permission. In interactive mode, the tool can ask for permission, but, with the `-y/--no-confirm` flag, permission can be given when calling the command with `-f/--force`:

    $ gftools packager "Family Serif" path/to/google/fonts/clone -p -y -f
    # or
    $ gftools packager "Family Serif" path/to/google/fonts/clone --pr --no-confirm --force

### Use a Local `upstream.yaml` File:

To add a new family or experiment with upstream configuration settings, it can be a good thing to use an `upstream.yaml` file directly from disk. Also, in case of a crash often caused by a problem in the upstream configuration, packager will ask to save a backup copy of the upstream configuration to disk. This file can be used to pick up work from the point of the crash, even if the `upstream.yaml` was created only in interactive mode.

    $ gftools packager path/to/family-serif.upstream.yaml path/to/google/fonts/clone [... flags]

Below is also a guide how to create an `upstream.yaml` file directly from the tool, using the `-u/--upstream-yaml` flag

### Workflow: Local Mastering Loop with QA

Suppose we want to add a super family with two siblings families on google/fonts. In this case we want to run the QA tooling locally before making the PR, to make sure the PR will run smoothly. We also want to iterate quickly between fixing upstream and running QA.

#### Create a Local `upstream.yaml`

Get started by creating a local `upstream.yaml` for quick access.

     $ gftools packager "Family Sans" familysans.upstream.yaml -u
     # or
     $ gftools packager "Family Sans" familysans.upstream.yaml --upstream-yaml

If "Family Sans" is already on google/fonts, `familysans.upstream.yaml` will get filled with as much info as available. Use -y/--no-confirm to skip interactive mode, you can always edit the file later:

    $ gftools packager "Family Sans" familysans.upstream.yaml -u -y
    # or
    $ gftools packager "Family Sans" familysans.upstream.yaml --upstream-yaml --no-confirm

To directly output the unchanged, original `upstream.yaml` template don't use a `name`:

    $ gftools packager familysans.upstream.yaml -u
    # or
    $ gftools packager familysans.upstream.yaml --upstream-yaml

You can also have a look at the [`upstream.yaml` template](../../Lib/gftools/template.upstream.yaml) now.

Now edit the the file according to your projects needs.

#### The `repository_url: local://` Hack

**NOTE:** To achieve a real quick local mastering loop, there's a hack built into the `upstram.yaml` `repository_url` property. You can use the `local://` prefix to reference a git repository path on your disk. This has two advantages for local development:

* no git clone of a repository from GitHub each time you run `gftool packager`
* no pushing necessary to your remote working branch.

You will however still have to commit changes to your local branch.

**CAUTION:** Google Fonts won't accept families where the METADATA.pb `source.repository_url` and `source.commit` hash are not publicly available. Consider the `local://` hack a temporary measure to get you up and running smoothly.

In your `familysans.upstream.yaml` you  can put a relative path, that will always be local to your current working directory (run `$ pwd` if unsure):

    # in file familysans.upstream.yaml
    repository_url: local://../font-projects/family-sans-font

Absolute paths are no problem either:

    # in file familysans.upstream.yaml
    repository_url: local:///home/username/font-projects/family-sans-font

Or use a `~` tilde shortcut to your home directory, perhaps the best option:

    # in file familysans.upstream.yaml
    repository_url: local://~/font-projects/family-sans-font

And the name of your feature brach, e.g:

    # in file familysans.upstream.yaml
    branch: mastering_v2.000_to_google_fonts
#### The QA – Mastering Loop

Now that you have set up prepared everything, start creating a package in the working directory of your local clone or fork of google/fonts. As mentioned before, especially for Font Bakery, this is optimal. Be careful with the `-f/--force` flag, if you are not sure what it does, don't use it, or read above and learn about it. You can also use the `-y/--no-confirm` flag.

    $ gftools familysans.upstream.yaml path/to/google/fonts/clone -fy

  If everything goes well, you will see a line like this in the output, that points you to where the package has been created:

    […]
    Package Directory: path/to/google/fonts/clone/ofl/familysans
    […]
    Done!

Now run `gftools qa` tools. It's initially OK to only run Font Bakery and to work on fixing all the FAIL stauses in the sources, but **this is the wrong place to teach details about the QA and mastering process.** *FIXME: Where is the right place?*:

    $ gftools qa -f path/to/google/fonts/clone/ofl/familysans/*.ttf --fontbakery -o ./font_out_qa
    # or use Font Bakery directly if you want to use its command line options directly
    $ fontbakery check-googlefonts path/to/google/fonts/clone/ofl/familysans/*.ttf

The results of the quality assurance tools should point you to enough issues that need work on your font project. After fixing these, repeat the local packaging and QA-ing. Once you are satisfied you can start preparing the PR.

#### Make a Pull Request

If you worked locally, as described in the previous sections, you should by now have an almost ready to go local file `familysans.upstream.yaml` with `local://` hack applied and a local repository of your font project, with a feature branch that contains all the latest mastering changes that you made. It's now time to get the changes of your feature branch merged into the projects repository main (usually `master`) branch. You can now change the `repository_url` and `branch` in your `familysans.upstream.yaml` file to the official project repository.

**NOTE:** as `branch` it is also possible to **reference a git tag**, such as a release tag if the project does tag releases, e.g. `tags/v1.000` for the tag `v1.000` or `tags/latest` for the tag `latest` do work as well. Use the `tags/` prefix to make it very clear that you are referencing a tag here.

The changed parts of your file should look similar to this:

    # in file familysans.upstream.yaml
    repository_url: https://github.com/foundry/family-sans-font.git
    branch: master

Now dispatch the PR and join the discussion on [google/fonts/pulls](https://github.com/google/fonts/pulls):

    $ gftools packager familysans.upstream.yaml path/to/google/fonts/clone -p -y

Congratulations, you set up the `upstream.yaml` for a font project from scratch. Future updates will be much simpler than this!

### Multi Family/Super Family/Bunch Updates

If e.g. a super family changes values that are shared between its sibling families, the right thing to do is to **make one PR with all changed sibling families in one go**. There are two ways the packager supports this. Lets assume that the `upstream.yaml` files for all siblings are already on google fonts and that they are still up to date, so there's no need to change them.

The direct way is use all siblings in one call, creating **one commit per sibling**, then send the commit directly:

    $ gftools packager "Family Sans" "Family Serif" "Family Mono" path/to/google/fonts/clone -p -y

Equivalently, this can be done incrementally, to make room for whatever needs to be done between the steps. In this case we pick a git branch name `-b/--branch` for the PR that describes our intend. To add to the branch we must use the `-a/--add-commit` flag.

This is supposed to create a new branch. Use `-f/--force` if the branch exists and you want to override it:

    $ gftools packager "Family Sans" path/to/google/fonts/clone -b update_family_sans-serif-mono -y

Start adding commits:

    $ gftools packager "Family Serif" path/to/google/fonts/clone -b update_family_sans-serif-mono -a -y
    # In between these operations you can add other commits to the branch, rebase etc.
    $ gftools packager "Family Mono" path/to/google/fonts/clone -b update_family_sans-serif-mono -a -y

You could have used `-p/--pr` to dispatch the commit directly with the last call. However, this way I can demonstrate that you don't need to add a package in order to make a PR for an existing branch:

    $ gftools packager path/to/google/fonts/clone -b update_family_sans-serif-mono -p

The `name` items can be zero or more in a call to the packager, however, without making a PR there's really no point in running the command at all. It's also possible to mix family names and `upstream.yaml` file names in one call to the packager, each  `name` is treated individually.

    $ gftools packager path/to/google/fonts/clone
    > No families to package.
    > Done!
