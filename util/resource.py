import json
import aiohttp
import hashlib
from io import BytesIO
from urllib.parse import quote
from typing import Awaitable, Dict, List, Set, Optional, Union

from PIL import Image

from .constance import *
from .upload import Uploader


class Character:
    def __init__(self, char_id: str, series: str, /, special: bool = False):
        self.series: str = series
        self.id: str = char_id
        self.names: Dict[str, str] = {}
        self.raw_avatars: Dict[str, str] = {}
        self.avatars: Dict[str, str] = {}
        self.type: Set[str] = set()
        self.tags: List[str] = []
        self.special = special

    def add_name(self, lang: str, name: str):
        self.names[lang] = name

    def add_avatar(self, avatar: str):
        self.raw_avatars[avatar] = f'avatar/{self.series}/{avatar}.webp'
        self.avatars[avatar] = quote(f'avatar/{self.series}/{avatar}.webp')

    def add_type(self, _type: str):
        self.type.add(_type)

    def add_tag(self, tag: str):
        if tag not in self.tags:
            self.tags.append(tag)

    @property
    def hash(self) -> str:
        return 'name:' + ','.join(sorted(self.names.values())) \
               + ' avatars:' + ','.join(sorted(self.avatars.keys())) \
               + ' types:' + ','.join(sorted(self.type)) \
               + ' tags:' + ','.join(self.tags)

    @property
    def is_invalid(self):
        return not self.avatars or not self.names

    def __repr__(self):
        return f'{self.id} names:{self.names} avatars:{self.avatars}'


class Resource:
    char_model = Character

    def __init__(self, series: str):
        self.series = series
        self.chars: Dict[str, Character] = {}
        self.client: Optional[aiohttp.ClientSession] = None
        self.upload: Optional[Uploader] = None

    async def req(self, url: str, target: str, byte: bool = False, **kwargs) -> Union[str, bytes]:
        async with self.client.get(url, **kwargs) as r:
            if r.status != 200:
                if r.status == 404:
                    raise FileNotFoundError(f'get {self.series} {target} failed {url} response 404')
                else:
                    raise AssertionError(f'get {self.series} {target} failed {url} {r.status}')
            return await r.read() if byte else await r.text()

    async def json(self, url: str, target: str, **kwargs):
        return json.loads(await self.req(url, target, **kwargs))

    @property
    def remote_version(self) -> Awaitable[str]:
        return self.req(static_url + version_url % self.series, 'version',
                        headers={'Referer': 'https://www.mayertalk.top'})

    @property
    def remote_data(self) -> Awaitable[dict]:
        return self.json(static_url + data_url % self.series, 'data',
                         headers={'Referer': 'https://www.mayertalk.top'})

    @property
    def special_char(self) -> Awaitable[dict]:
        return self.json(static_url + special_data_url % self.series, 'special_data',
                         headers={'Referer': 'https://www.mayertalk.top'})

    def char(self, char_id, /, special: bool = False) -> Character:
        if char_id not in self.chars:
            self.chars[char_id] = self.char_model(char_id, self.series, special=special)
            self.chars[char_id].add_tag(self.series)
        return self.chars[char_id]

    def clean(self):
        for char_id, char in self.chars.copy().items():
            if char.is_invalid:
                self.chars.pop(char_id)
                print(f'[WARNING] invalid {self.series} char {char_id}')

    @property
    def version(self) -> str:
        string = ''.join(char.hash for char in sorted(self.chars.values(), key=lambda x: x.id))
        return hashlib.md5(string.encode('utf-8')).hexdigest()

    @property
    def data(self) -> dict:
        return {
            char_id: {
                'names': dict(sorted(data.names.items(), key=lambda x: x[0])),
                'avatars': list(sorted(data.avatars.values())),
                'tags': data.tags
            }
            for char_id, data in self.chars.items()
        }

    async def run(self):
        self.client = aiohttp.ClientSession()

        try:
            res = await self.special_char
        except (AssertionError, FileNotFoundError):
            res = {}

        for char_id, data in res.items():
            char = self.char(char_id, special=True)
            for lang, name in data['names'].items():
                char.add_name(lang, name)
            for i, url in enumerate(data['avatars']):
                char.avatars[str(i)] = url
            print(f'special char {self.series} {char.id}')

    async def get_avatar_data(self, char: Character, avatar: str) -> bytes:
        ...

    async def upload_avatar(self, char: Character, avatar: str):
        try:
            im = Image.open(BytesIO(await self.get_avatar_data(char, avatar)))
            out_put = BytesIO()
            im.save(out_put, 'webp')
            out_put.seek(0)
            await self.upload(char.raw_avatars[avatar], out_put.read())
            print(f'upload {self.series} {char.raw_avatars[avatar]}')
        except FileNotFoundError as e:
            print(f'upload {self.series} {char.raw_avatars[avatar]} failed {e.args[0]}')
            char.avatars.pop(avatar)
            char.raw_avatars.pop(avatar)

    async def update(self):
        self.clean()
        self.upload = Uploader(self.client)
        version = self.version
        if await self.remote_version == version:
            print(f'pass {self.series} {version}')
            return

        print(f'update {self.series} {version}')
        remote_data = await self.remote_data
        for char_id, char in self.chars.items():
            if char.special:
                continue
            if char_id in remote_data:
                for avatar, url in char.avatars.copy().items():
                    if url not in remote_data[char_id]['avatars']:
                        await self.upload_avatar(char, avatar)
            else:
                for avatar, url in char.avatars.copy().items():
                    await self.upload_avatar(char, avatar)

        self.clean()

        version = self.version
        await self.upload(version_url % self.series, version.encode('utf-8'))
        print(f'upload {self.series} version {version}')

        await self.upload(data_url % self.series, json.dumps(self.data, ensure_ascii=False).encode('utf-8'))
        print(f'upload {self.series} data')
