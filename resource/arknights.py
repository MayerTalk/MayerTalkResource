import asyncio
from typing import Dict
from urllib.parse import quote

from pypinyin import lazy_pinyin, Style

from util.resource import Resource, Character


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
    char_data_url = 'https://github.com/Kengxxiao/ArknightsGameData/raw/master/%s/gamedata/excel/character_table.json'
    char_skin_url = 'https://github.com/Kengxxiao/ArknightsGameData/raw/master/zh_CN/gamedata/excel/skin_table.json'
    char_avatar_url = 'https://github.com/yuanyan3060/Arknights-Bot-Resource/raw/main/avatar/%s.png'
    enemy_data_url = 'https://github.com/Kengxxiao/ArknightsGameData/raw/master/%s/gamedata/excel/enemy_handbook_table.json'
    enemy_avatar_url = 'https://github.com/yuanyan3060/Arknights-Bot-Resource/raw/main/enemy/%s.png'
    chars: Dict[str, ArknightsCharacter]
    char_model = ArknightsCharacter

    async def parse(self, lang):
        res: dict = await self.json(self.char_data_url % lang, 'char_data')
        print('get arknights %s char data' % lang)
        for char_id, data in res.items():
            char = self.char(char_id)
            char.add_name(lang, data['name'])
            if lang == 'zh_CN':
                char.add_name('py', ''.join(lazy_pinyin(data['name'])))
                char.add_name('fpy', ''.join(lazy_pinyin(data['name'], style=Style.FIRST_LETTER)))
                if data['profession'] == 'NONE':
                    char.add_tag('trap')
                elif data['profession'] == 'TOKEN':
                    char.add_tag('token')
                else:
                    char.add_tag('operator')
                if data['displayNumber']:
                    char.add_name('code', data['displayNumber'])

        res: dict = await self.json(self.enemy_data_url % lang, 'enemy_data')
        print('get arknights %s enemy data' % lang)
        for enemy_id, data in res.items():
            char = self.enemy(enemy_id)
            char.add_name(lang, data['name'])
            if lang == 'zh_CN':
                char.add_name('py', ''.join(lazy_pinyin(data['name'])))
                char.add_name('fpy', ''.join(lazy_pinyin(data['name'], style=Style.FIRST_LETTER)))
                char.add_name('code', data['enemyIndex'])
                char.add_avatar(enemy_id)
                char.add_tag('enemy')

    async def run(self):
        await super().run()
        await asyncio.gather(*[self.parse(lang) for lang in self.langs])

        skins = await self.json(self.char_skin_url, 'skin_data')
        for data in skins['charSkins'].values():
            self.char(data['charId']).add_avatar(data['avatarId'])

        await self.update()

    def start(self):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(self.run())

    def _char(self, char_id: str, is_enemy: bool, /, special: bool = False) -> ArknightsCharacter:
        if char_id not in self.chars:
            self.chars[char_id] = self.char_model(char_id, self.series, is_enemy, special=special)
            self.chars[char_id].add_tag(self.series)
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
