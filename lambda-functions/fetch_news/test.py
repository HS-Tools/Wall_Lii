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
    test_insert_patch(use_blog=True)


if __name__ == "__main__":
    main()
