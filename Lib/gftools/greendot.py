"""
David Berlow's Green Dot algorithm:
https://docs.google.com/document/d/15652Yabs0prnocpjG1TxG6zrfFSIYqOwlSIMkdbgqfg/edit?resourcekey=0-DXNZQLV2TbSqyn9HCLfhFA
"""
from collections import OrderedDict
import sys


size_ranges = OrderedDict(
    {
        (6, 12): [6, 7, 8, 9, 10, 11, 12],
        (12, 18): [12, 14, 18],
        (18, 32): [18, 24, 28, 32],
        (32, 54): [32, 36, 48, 54],
        (54, 144): [54, 60, 72, 96, 120, 144],
    }
)

DOC_SIZES = [6, 7, 8, 9, 10, 11, 12, 14, 18, 24, 28, 36, 48, 60, 72, 96, 120, 144]

SEGMENT_COUNT = 6


def pin(n):
    return min(DOC_SIZES, key=lambda x: abs(x - n))


def mid(a, b):
    return (a + b) / 2


def green_dot(min_opsz, max_opsz):
    pos_1 = get_first_pos(min_opsz, max_opsz)
    pos_5 = get_fifth_pos(min_opsz, max_opsz)
    pos_3 = get_third_pos(min_opsz, max_opsz)
    pos_2 = mid(pos_1, pos_3)
    pos_4 = mid(pos_3, pos_5)
    if pos_5 - pos_1 < 3:
        return [pos_1, pos_5]
    return sorted(set(pin(o) for o in (pos_1, pos_2, pos_3, pos_4, pos_5)))


def get_first_pos(min_opsz, max_opsz):
    for smallest, largest in size_ranges:
        if min_opsz <= smallest and max_opsz >= largest:
            return mid(smallest, largest)
    return min_opsz


def get_fifth_pos(min_opsz, max_opsz):
    best_range = None
    for smallest, largest in size_ranges:
        if min_opsz <= smallest and max_opsz >= largest:
            best_range = (smallest, largest)
    if not best_range:
        return max_opsz

    best_range = size_ranges[best_range]
    if len(best_range) != 2:
        mid = best_range[int(len(best_range) / 2)]
    else:
        mid = best_range[int(len(best_range) / 2) - 1]
    return int((max_opsz + mid) / 2)


def get_third_pos(min_opsz, max_opsz):
    segment_size = (max_opsz - min_opsz) / SEGMENT_COUNT
    return min_opsz + 1.5 * segment_size


def parse_range(string):
    return tuple(map(int, string.split(",")))


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python -m gftools.greendot 0,10")
        sys.exit()
    opsz_range = parse_range(sys.argv[1])
    print(green_dot(*opsz_range))
