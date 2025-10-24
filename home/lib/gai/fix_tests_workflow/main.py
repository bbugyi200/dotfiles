import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from workflow_base import BaseWorkflow


class FixTestsWorkflow(BaseWorkflow):
    """A workflow for fixing failing tests using an edit + test + collect context + research loop."""
