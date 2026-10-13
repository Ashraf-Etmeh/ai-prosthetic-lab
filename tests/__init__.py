"""The test package. Importing it switches the Claude API off for every test.

`python -m unittest` (and `python -m unittest tests.test_x`) imports this
package first, so no test can reach the API, even on a machine where an
API key is set: reasoning/writer.py default_writer() then returns a writer
that is always unavailable. Tests that need answers pass a FakeWriter
(tests/helpers.py).
"""

import os

from shared.config import OFFLINE_ENV

os.environ[OFFLINE_ENV] = "1"
