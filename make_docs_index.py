#!/usr/bin/env python3

import argparse
import sys

from pathlib import Path
from typing import Generator, Iterable

import mistletoe as md


def parse_args(args=None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Create an index page for all markdown content in a directory")

    parser.add_argument('-i', '--index-dir', metavar="DIR",
                        help="Directory to index (CWD will be used if not specified)",
                        default=Path.cwd(),
                        type=Path)
    parser.add_argument('-o', '--output-filename', type=str, default='docs_index.md',
                        help="Name of index file to be created in index directory")
    parser.add_argument('-s', '--skip', type=Path, action='append', help="Skip this item")
    parser.add_argument('-v', '--verbose', action='store_true', help="Verbose")

    opts = parser.parse_args(args)

    if not opts.index_dir.is_dir():
        parser.error(f"Specified input {opts.index_dir} is not a directory")

    if not opts.output_filename:
        opts.output_filename = "docs_index.md"

    return opts


class HeadingEntry:
    def __init__(self, file_path: Path, level: int, text: str) -> None:
        if level is None or level < 1 or level > 6:
            raise ValueError(f"level '{level}' is out of the allowed range 1-6")
        if not file_path:
            raise ValueError("Empty file_path argument")
        if not text:
            raise ValueError("Empty heading text argument")

        self._path = file_path
        self._level = level
        self._text = text.strip()

    @property
    def text(self):
        return self._text

    @property
    def level(self):
        return self._level

    @property
    def path(self):
        return self._path


def parse_file(md_file: Path) -> Iterable[HeadingEntry]:
    with open(md_file) as f:
        doc = md.Document(f)

    return [HeadingEntry(md_file, h.level, h.children[0].content)
            for h in filter(lambda x: isinstance(x, md.block_token.Heading), doc.children)]


def write_output(base_dir: Path,
                 headings: Iterable[HeadingEntry],
                 index_filename: str,
                 title: str = "Documentation Index") -> None:
    # this implementation doesn't work well with non-ASCII text
    def make_group_name(entry: HeadingEntry) -> str:
        first_char = entry.text[0]
        if first_char.isalpha():
            return first_char.upper()
        return "Other"

    def make_sort_key(entry: HeadingEntry) -> str:
        if entry.text[0].isalpha():
            return entry.text.casefold()
        return '~'  # last printable character in ASCII

    def make_link(target: Path) -> str:
        return str(target.relative_to(base_dir))

    headings = sorted(headings, key=make_sort_key)

    with Path(base_dir, index_filename).open('w') as f_output:
        def write_group_heading(text): f_output.write(f"\n## {text}\n\n")

        f_output.write(f"# {title}\n")
        if len(headings) == 0:
            return

        current_group = make_group_name(headings[0])
        write_group_heading(current_group)
        for item in headings:
            group = make_group_name(item)
            if group != current_group:
                current_group = group
                write_group_heading(current_group)
            f_output.write(f"* [{item.text}]({make_link(item.path)})\n")


def find_markdown_files(base_dir: Path, skip_items: Iterable) -> Generator[Path, None, None]:
    for path in base_dir.iterdir():
        if path.name[0] not in ('.', '_') and path.resolve() not in skip_items:
            if path.is_file() and path.suffix == '.md':
                yield path
            if path.is_dir():
                yield from find_markdown_files(path, skip_items)


def main(args=None):
    opts = parse_args(args)

    index_dir = opts.index_dir.resolve(strict=True)
    output_path = Path(index_dir, opts.output_filename).resolve()
    items_to_skip = set(p.resolve() for p in opts.skip)
    items_to_skip.add(output_path)

    heading_list = []
    for path in find_markdown_files(index_dir, items_to_skip):
        if opts.verbose:
            print("parsing", path, file=sys.stderr)
        heading_list.extend(parse_file(path))

    if opts.verbose:
        print("Writing index file", output_path, file=sys.stderr)
    write_output(index_dir, heading_list, opts.output_filename)


if __name__ == '__main__':
    main(sys.argv[1:])
