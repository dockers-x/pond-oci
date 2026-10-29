#!/usr/bin/env python3
import argparse
import copy
import json
from pathlib import Path
import re
import tomllib


def version(tag, base, approved):
    if tag != f'v{approved}' or not re.fullmatch(re.escape(f'v{base}') + r'-rc\.[1-9][0-9]*', tag):
        raise ValueError('only an RC tag matching image.toml is supported')
    return tag[1:]


def verify_config(original, promoted, expected):
    original = copy.deepcopy(original)
    promoted = copy.deepcopy(promoted)
    label = 'org.opencontainers.image.version'
    if promoted['config']['Labels'].pop(label) != expected:
        raise ValueError('incorrect promoted version')
    original['config']['Labels'].pop(label)
    if original != promoted:
        raise ValueError('promotion changed more than the version label')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('tag')
    parser.add_argument('--original', type=Path)
    parser.add_argument('--promoted', type=Path)
    arguments = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    approved = json.loads((root / 'release-candidate.json').read_text())['approved_version']
    expected = version(arguments.tag, tomllib.loads((root / 'image.toml').read_text())['version'], approved)
    if arguments.original or arguments.promoted:
        if not (arguments.original and arguments.promoted):
            parser.error('both config paths are required')
        verify_config(json.loads(arguments.original.read_text()), json.loads(arguments.promoted.read_text()), expected)
    print(expected)


if __name__ == '__main__':
    main()
