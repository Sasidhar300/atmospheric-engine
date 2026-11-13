import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from scripts import workspace


class WorkspaceTests(unittest.TestCase):
    def test_handoff_format(self):
        self.assertEqual(workspace.check(), 0)

    def test_graph_hash_requires_matching_source_and_output(self):
        with TemporaryDirectory() as directory:
            graph = Path(directory) / "graph.json"
            stamp = Path(directory) / "atmosphere-inputs.json"
            graph.write_bytes(b"graph")
            stamp.write_text(json.dumps({
                "inputs": "source",
                "graph": hashlib.sha256(graph.read_bytes()).hexdigest(),
            }))
            with patch.multiple(workspace, GRAPH=graph.parent, STAMP=stamp):
                with patch.object(workspace, "input_hash", return_value="edited source"):
                    self.assertEqual(workspace.graph_status(), "missing or stale")
                with patch.object(workspace, "input_hash", return_value="source"):
                    self.assertEqual(workspace.graph_status(), "current for indexed source")
                    graph.write_bytes(b"changed graph")
                    self.assertEqual(workspace.graph_status(), "missing or stale")

    def test_query_rejects_stale_graph_before_invoking_cli(self):
        with patch.dict("os.environ", {"Q": "audio_metrics"}), \
             patch.object(workspace, "graph_status", return_value="missing or stale"), \
             patch.object(workspace.subprocess, "run") as run:
            with self.assertRaisesRegex(ValueError, "stale"):
                workspace.graph_command("query")
            run.assert_not_called()
