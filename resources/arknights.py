import asyncio
from typing import Dict
from urllib.parse import quote

from pypinyin import lazy_pinyin, Style

from util.resource import Resource, Character
from util.cc import s2t


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
