import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import AsyncMock, Mock

from resources.arknights_npc import ArknightsNPCSource, build_source_files, changed_files


class ArknightsNPCResourceTests(unittest.TestCase):
    def test_maps_character_and_diff_paths(self):
        files = build_source_files([
            {'path': 'export/avg_003_kalts_1/1$1.png', 'type': 'blob', 'sha': 'png-sha'},
            {'path': 'export_webp/avg_003_kalts_1/1$1.webp', 'type': 'blob', 'sha': 'webp-sha'},
            {'path': 'arknights_npc.json', 'type': 'blob', 'sha': 'data-sha'},
            {'path': 'README.md', 'type': 'blob', 'sha': 'readme-sha'},
            {'path': 'export/avg_003_kalts_1', 'type': 'tree', 'sha': 'tree-sha'},
        ])

        self.assertEqual(
            files['avatar/arknights_npc/avg_003_kalts_1/1$1.png'].source_path,
            'export/avg_003_kalts_1/1$1.png',
        )
        self.assertEqual(
            files['avatar/arknights_npc/avg_003_kalts_1/1$1.webp'].source_path,
            'export_webp/avg_003_kalts_1/1$1.webp',
        )
        self.assertIn('char/arknights_npc.json', files)
        self.assertEqual(len(files), 3)

    def test_selects_only_new_or_changed_files(self):
        previous = build_source_files([
            {'path': 'export/character/old.png', 'type': 'blob', 'sha': 'old'},
            {'path': 'export/character/same.png', 'type': 'blob', 'sha': 'same'},
            {'path': 'arknights_npc.json', 'type': 'blob', 'sha': 'metadata-old'},
        ])
        current = build_source_files([
            {'path': 'export/character/old.png', 'type': 'blob', 'sha': 'new'},
            {'path': 'export/character/same.png', 'type': 'blob', 'sha': 'same'},
            {'path': 'export/character/new.png', 'type': 'blob', 'sha': 'new-file'},
            {'path': 'arknights_npc.json', 'type': 'blob', 'sha': 'metadata-new'},
        ])

        self.assertEqual(
            [file.target_path for file in changed_files(previous, current)],
            [
                'avatar/arknights_npc/character/new.png',
                'avatar/arknights_npc/character/old.png',
                'char/arknights_npc.json',
            ],
        )


class ArknightsNPCSyncTests(unittest.IsolatedAsyncioTestCase):
    async def test_upload_failure_does_not_advance_source_state(self):
        current = build_source_files([
            {'path': 'export/character/diff.png', 'type': 'blob', 'sha': 'image'},
            {'path': 'arknights_npc.json', 'type': 'blob', 'sha': 'metadata'},
        ])
        resource = ArknightsNPCSource()
        resource.commit = AsyncMock(return_value=('current-commit', 'current-tree'))
        resource.tree = AsyncMock(return_value=current)
        resource.upload_file = AsyncMock(side_effect=RuntimeError('upload failed'))
        resource.commit_state = Mock()

        with TemporaryDirectory() as directory:
            resource.source_state_path = Path(directory) / 'arknights_npc.source.json'
            with self.assertRaisesRegex(RuntimeError, 'upload failed'):
                await resource.run()
            self.assertFalse(resource.source_state_path.exists())

        resource.commit_state.assert_not_called()


if __name__ == '__main__':
    unittest.main()
