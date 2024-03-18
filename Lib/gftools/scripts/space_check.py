#!/usr/bin/env python3
#
# Copyright 2017 Google Inc. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS-IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
"""Utility to sanity check whitespace chars in fonts.

Not in sanity_check because it can yield false positives. For example,
Material Icons correctly doesn't include a space. If metadata awareness
was added it could move into sanity_check.

"""


def main():
    print(
        "This code has been deprecated; use fontbakery checks\n"
        "com.google.fonts/check/whitespace_ink and\n"
        "com.google.fonts/check/whitespace_widths instead"
    )


if __name__ == "__main__":
    main()
