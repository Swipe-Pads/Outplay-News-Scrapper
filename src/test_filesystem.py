"""
Filesystem test for SwipePads News Scraper.
Verifies that we can create, read, and delete files in the data directory.
"""

import os
from pathlib import Path
from datetime import datetime


def test_filesystem():
    """
    Test filesystem operations:
    1. Create a file in data/ directory
    2. Write timestamp to it
    3. Read it back and verify
    4. Delete the file
    5. Verify deletion
    """
    # Get project root (parent of src/)
    project_root = Path(__file__).parent.parent
    data_dir = project_root / 'data'
    test_file = data_dir / 'test.txt'

    try:
        # Ensure data directory exists
        data_dir.mkdir(exist_ok=True)

        # Step 1: Create and write to file
        timestamp = datetime.now().isoformat()
        test_content = f"Filesystem test - Created at: {timestamp}\n"

        with open(test_file, 'w') as f:
            f.write(test_content)

        print(f"✅ Created file: {test_file}")

        # Step 2: Read back and verify
        with open(test_file, 'r') as f:
            read_content = f.read()

        if read_content == test_content:
            print(f"✅ File contents verified")
        else:
            print(f"❌ Content mismatch!")
            print(f"   Expected: {test_content}")
            print(f"   Got: {read_content}")
            return False

        # Step 3: Verify file exists
        if not test_file.exists():
            print(f"❌ File does not exist after creation!")
            return False

        # Step 4: Delete the file
        test_file.unlink()
        print(f"✅ File deleted successfully")

        # Step 5: Verify deletion
        if test_file.exists():
            print(f"❌ File still exists after deletion!")
            return False

        print(f"✅ Filesystem test: PASSED")
        return True

    except Exception as e:
        print(f"❌ Filesystem test FAILED with error: {e}")
        # Clean up on error
        if test_file.exists():
            test_file.unlink()
        return False


if __name__ == '__main__':
    success = test_filesystem()
    exit(0 if success else 1)
