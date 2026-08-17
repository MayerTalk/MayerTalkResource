import unittest
from unittest.mock import AsyncMock, patch

from resources.arknights import (
    ArknightsCharacter,
    ArknightsResource,
    available_avatar_names,
    filter_missing_avatars,
)


class AvailableAvatarNamesTests(unittest.TestCase):
    def test_extracts_png_blob_names(self):
        entries = [
            {'path': 'char_002_amiya.png', 'type': 'blob', 'sha': 'a'},
            {'path': 'char_002_amiya_epoque#4.png', 'type': 'blob', 'sha': 'b'},
            {'path': 'char_002_amiya_1+.png', 'type': 'blob', 'sha': 'c'},
            {'path': 'char_002_amiya_2.png', 'type': 'blob', 'sha': 'd'},
            {'path': 'char_002_amiya.webp', 'type': 'blob', 'sha': 'e'},
            {'path': 'subfolder', 'type': 'tree', 'sha': 'f'},
        ]

        self.assertEqual(
            available_avatar_names(entries),
            {'char_002_amiya', 'char_002_amiya_epoque#4', 'char_002_amiya_1+', 'char_002_amiya_2'},
        )

    def test_handles_empty_listing(self):
        self.assertEqual(available_avatar_names([]), set())


class FilterMissingAvatarsTests(unittest.TestCase):
    def test_drops_unavailable_and_keeps_existing(self):
        available = {
            'avatar': {'char_002_amiya', 'char_002_amiya_2'},
            'enemy': {'enemy_10001_trslim'},
        }

        operator = ArknightsCharacter('char_002_amiya', 'arknights')
        operator.add_avatar('char_002_amiya')
        operator.add_avatar('char_002_amiya_2')
        operator.add_avatar('char_002_amiya_epoque#4')  # missing

        enemy = ArknightsCharacter('enemy_10001_trslim', 'arknights', True)
        enemy.add_avatar('enemy_10001_trslim')
        enemy.add_avatar('enemy_10001_trslim_2')  # missing

        trap = ArknightsCharacter('trap_003_gate', 'arknights')
        trap.add_avatar('trap_003_gate')  # missing

        chars = {'char_002_amiya': operator, 'enemy_10001_trslim': enemy, 'trap_003_gate': trap}

        dropped = filter_missing_avatars(chars, available)

        self.assertEqual(dropped, 3)
        self.assertEqual(set(operator.avatars), {'char_002_amiya', 'char_002_amiya_2'})
        self.assertEqual(set(enemy.avatars), {'enemy_10001_trslim'})
        self.assertEqual(set(trap.avatars), set())

    def test_skips_special_chars(self):
        available = {'avatar': set(), 'enemy': set()}

        special = ArknightsCharacter('doctor', 'arknights', special=True)
        special.add_avatar('doctor')

        chars = {'doctor': special}

        dropped = filter_missing_avatars(chars, available)

        self.assertEqual(dropped, 0)
        self.assertEqual(set(special.avatars), {'doctor'})


class ArknightsResourceFilterTests(unittest.IsolatedAsyncioTestCase):
    async def test_fetch_available_avatars_returns_none_on_failure(self):
        resource = ArknightsResource
        with patch.object(resource, 'available_names', AsyncMock(side_effect=FileNotFoundError('404'))) as mock_names:
            result = await resource.fetch_available_avatars()

        self.assertIsNone(result)
        mock_names.assert_awaited()

    async def test_available_names_parses_tree_response(self):
        resource = ArknightsResource
        resource.json = AsyncMock(return_value={
            'truncated': False,
            'tree': [
                {'path': 'char_002_amiya.png', 'type': 'blob', 'sha': 'a'},
                {'path': 'readme.txt', 'type': 'blob', 'sha': 'b'},
            ],
        })

        names = await resource.available_names('avatar')

        self.assertEqual(names, {'char_002_amiya'})


if __name__ == '__main__':
    unittest.main()