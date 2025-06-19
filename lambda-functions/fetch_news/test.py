#!/usr/bin/env python3
"""
Test runner for fetch_news lambda's test_insert_patch function.
"""

from lambda_function import test_insert_patch


def main():
    # Run test using tracker API (default)
    # print("Running test_insert_patch with tracker API...")
    # test_insert_patch(use_blog=False)

    # Run test using blog API
    print("Running test_insert_patch with blog API...")
    test_insert_patch(use_blog=False)

    # Test worked well for this blog: https://hearthstone.blizzard.com/en-us/news/24205944
    # Tested https://us.forums.blizzard.com/en/hearthstone/t/3241-hotfix-patch/146937 and had to add a trinket cost section and clarify not to have blank sections for armor


if __name__ == "__main__":
    main()
