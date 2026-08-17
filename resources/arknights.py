import asyncio
from typing import Dict, Optional
from urllib.parse import quote

from pypinyin import lazy_pinyin, Style

from util.resource import Resource, Character, ServerError
from util.cc import s2t


def available_avatar_names(entries: list) -> set:
    """Extract the base names of top-level .png blobs from a git tree listing."""
    names = set()
    for entry in entries or []:
        if entry.get('type') != 'blob':
            continue
        path = entry.get('path')
        if isinstance(path, str) and path.endswith('.png'):
            names.add(path[:-4])
    return names


def filter_missing_avatars(chars: Dict[str, 'ArknightsCharacter'], available: Dict[str, set]) -> int:
    """Drop avatars whose png does not exist in ArknightsGameResource.

    Operator/token/trap avatars must exist in avatar/, enemy avatars in enemy/.
    Special chars (remote spec data) are left untouched.
    """
    dropped = 0
    for char in chars.values():
        if char.special:
            continue
        pool = available['enemy'] if char.is_enemy else available['avatar']
        for avatar_id in list(char.avatars):
            if avatar_id not in pool:
                print(f'[FILTER] {char.id} drop avatar {avatar_id} (missing in ArknightsGameResource)')
                del char.avatars[avatar_id]
                dropped += 1
    return dropped


class ArknightsCharacter(Character):
    def __init__(self, char_id: str, series: str, is_enemy: bool = False, /, special: bool = False):
        super().__init__(char_id, series, special=special)
        self.is_enemy: bool = is_enemy


class ArknightsResource(Resource):
    langs = [
        'zh_CN',
        'en_US',
        'ja_JP',
    ]
    main_url = 'https://github.com/Kengxxiao/ArknightsGameData/raw/master/'
    yostar_url = 'https://github.com/Kengxxiao/ArknightsGameData_YoStar/raw/main/'
    char_data_url = '%s/gamedata/excel/character_table.json'
    enemy_data_url = '%s/gamedata/excel/enemy_handbook_table.json'
    char_skin_url = 'https://github.com/Kengxxiao/ArknightsGameData/raw/master/zh_CN/gamedata/excel/skin_table.json'
    char_avatar_url = 'https://github.com/yuanyan3060/ArknightsGameResource/raw/main/avatar/%s.png'
    enemy_avatar_url = 'https://github.com/yuanyan3060/ArknightsGameResource/raw/main/enemy/%s.png'
    game_resource_api = 'https://api.github.com/repos/yuanyan3060/ArknightsGameResource'
    avatar_tree_url = game_resource_api + '/git/trees/main:%s'
    chars: Dict[str, ArknightsCharacter]
    char_model = ArknightsCharacter

    def data_url(self, lang: str, t: str):
        if t == 'char':
            url = self.char_data_url % lang
        elif t == 'enemy':
            url = self.enemy_data_url % lang
        else:
            raise ValueError('unknown data url type %s' % t)
        if lang == 'zh_CN':
            return self.main_url + url
        else:
            return self.yostar_url + url

    async def parse(self, lang):
        res: dict = await self.json(self.data_url(lang, 'char'), 'char_data')
        print('get arknights %s char data' % lang)
        for char_id, data in res.items():
            char = self.char(char_id)
            char.add_name(lang, data['name'])
            if lang == 'zh_CN':
                char.add_name('zh_TW', s2t(data['name']))
                char.add_name('py', ''.join(lazy_pinyin(data['name'])))
                char.add_name('fpy', ''.join(lazy_pinyin(data['name'], style=Style.FIRST_LETTER)))
                if data['profession'] == 'TRAP':
                    char.add_tag('trap')
                elif data['profession'] == 'TOKEN':
                    char.add_tag('token')
                else:
                    char.add_tag('operator')
                if data['displayNumber']:
                    char.add_name('code', data['displayNumber'])

        res: dict = await self.json(self.data_url(lang, 'enemy'), 'enemy_data')
        if 'enemyData' in res:
            res = res['enemyData']

        print('get arknights %s enemy data' % lang)
        for enemy_id, data in res.items():
            char = self.enemy(enemy_id)
            char.add_name(lang, data['name'])

            if lang == 'zh_CN':
                char.add_name('py', ''.join(lazy_pinyin(data['name'])))
                char.add_name('fpy', ''.join(lazy_pinyin(data['name'], style=Style.FIRST_LETTER)))
                char.add_name('code', data['enemyIndex'])
                char.add_name('zh_TW', s2t(data['name']))
                char.add_avatar(enemy_id)
                char.add_tag('enemy')

    async def available_names(self, folder: str) -> set:
        """List the png base names available in an ArknightsGameResource folder."""
        error = None
        for attempt in range(3):
            try:
                res: dict = await self.json(self.avatar_tree_url % folder, folder + '_tree')
                if res.get('truncated'):
                    raise AssertionError(f'get {self.series} {folder} tree truncated')
                return available_avatar_names(res.get('tree') or [])
            except (AssertionError, FileNotFoundError, ServerError, ValueError) as e:
                error = e
                if attempt < 2:
                    print(f'retry get {self.series} {folder} tree (attempt {attempt + 1})')
                    await asyncio.sleep(2 ** attempt)
        raise error

    async def fetch_available_avatars(self) -> Optional[Dict[str, set]]:
        """Map 'avatar'/'enemy' to the png base names available in ArknightsGameResource.

        Returns None (filtering is skipped for this run) when the listings cannot be fetched.
        """
        try:
            avatar, enemy = await asyncio.gather(
                self.available_names('avatar'),
                self.available_names('enemy'),
            )
            return {'avatar': avatar, 'enemy': enemy}
        except (AssertionError, FileNotFoundError, ServerError, ValueError) as e:
            print(f'[WARNING] fetch available avatars failed {e}; skip pre-filter')
            return None

    async def run(self):
        await super().run()
        await asyncio.gather(*[self.parse(lang) for lang in self.langs])

        skins = await self.json(self.char_skin_url, 'skin_data')
        for data in skins['charSkins'].values():
            self.char(data['charId']).add_avatar(data['avatarId'])

        available = await self.fetch_available_avatars()
        if available is not None:
            filter_missing_avatars(self.chars, available)

        await self.update()

    def start(self):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(self.run())

    def _char(self, char_id: str, is_enemy: bool, /, special: bool = False) -> ArknightsCharacter:
        if char_id not in self.chars:
            self.chars[char_id] = self.char_model(char_id, self.series, is_enemy, special=special)
        return self.chars[char_id]

    def char(self, char_id: str, /, special: bool = False) -> ArknightsCharacter:
        return self._char(char_id, False, special=special)

    def enemy(self, enemy_id: str) -> ArknightsCharacter:
        return self._char(enemy_id, True)

    async def get_avatar_data(self, char: ArknightsCharacter, avatar: str) -> bytes:
        if char.is_enemy:
            return await self.req(self.enemy_avatar_url % quote(avatar), 'enemy_avatar', True)
        else:
            return await self.req(self.char_avatar_url % quote(avatar), 'char_avatar', True)


ArknightsResource = ArknightsResource('arknights')
