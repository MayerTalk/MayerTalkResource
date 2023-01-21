import os
import time
import hashlib
import aiohttp

from typing import Awaitable

server = os.environ.get('SERVER')
key = os.environ.get('KEY')

class Uploader:
    def __init__(self, client: aiohttp.ClientSession):
        self.client = client

    @property
    def sign(self) -> dict:
        ts = str(int(time.time()))
        signature = hashlib.sha256(f'{key}MTS{ts}'.encode('utf-8')).hexdigest()
        return {'signature': signature, 'timestamp': ts}

    async def upload(self, path: str, file: bytes):
        async with self.client.put(server, headers=self.sign, params={'path': path, 'site': 'static'},
                                   data={'file': file}) as r:
            assert r.ok, 'upload %s failed %s' % (path, r.status)
            res = await r.json()
            assert res['code'] == 200, 'upload %s failed [%s]' % (path, res['code'])
            return True

    def __call__(self, path: str, file: bytes) -> Awaitable:
        return self.upload(path, file)
