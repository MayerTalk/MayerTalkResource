import asyncio
import json
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import quote

import aiohttp

from util.time import get_time
from util.upload import Uploader


@dataclass(frozen=True)
class SourceFile:
    source_path: str
    target_path: str
    sha: str


def build_source_files(tree: list[dict[str, Any]]) -> dict[str, SourceFile]:
    """Map source-tree blobs to their static-server destinations."""
    files: dict[str, SourceFile] = {}
    prefixes = (
        ('export/', 'avatar/arknights_npc/'),
        ('export_webp/', 'avatar/arknights_npc/'),
    )

    for entry in tree:
        if entry.get('type') != 'blob':
            continue

        source_path = entry.get('path')
        sha = entry.get('sha')
        if not isinstance(source_path, str) or not isinstance(sha, str):
            continue

        target_path = None
        if source_path == 'arknights_npc.json':
            target_path = 'char/arknights_npc.json'
        else:
            for source_prefix, target_prefix in prefixes:
                if source_path.startswith(source_prefix):
                    target_path = target_prefix + source_path.removeprefix(source_prefix)
                    break

        if target_path is None:
            continue
        if target_path in files:
            raise ValueError(f'duplicate target path {target_path}')
        files[target_path] = SourceFile(source_path, target_path, sha)

    if 'char/arknights_npc.json' not in files:
        raise ValueError('arknights_npc.json is missing from the source tree')
    return files


def changed_files(previous: dict[str, SourceFile], current: dict[str, SourceFile]) -> list[SourceFile]:
    return [current[path] for path in sorted(current) if previous.get(path) != current[path]]


class ArknightsNPCSource:
    api_url = 'https://api.github.com/repos/Arkfans/ArknightsAvatarResource'
    raw_url = 'https://raw.githubusercontent.com/Arkfans/ArknightsAvatarResource/%s/%s'
    source_state_path = Path('version/arknights_npc.source.json')
    concurrency = 16

    def __init__(self):
        self.client: aiohttp.ClientSession | None = None
        self.upload: Uploader | None = None

    async def request(self, url: str, target: str, *, byte: bool = False) -> bytes | dict[str, Any]:
        assert self.client is not None
        async with self.client.get(url) as response:
            if response.status != 200:
                raise RuntimeError(f'get arknights npc {target} failed {url} {response.status}')
            return await response.read() if byte else await response.json()

    async def commit(self, ref: str) -> tuple[str, str]:
        data = await self.request(f'{self.api_url}/commits/{quote(ref, safe="")}', 'commit')
        assert isinstance(data, dict)
        commit_sha = data.get('sha')
        tree = data.get('commit', {}).get('tree', {})
        tree_sha = tree.get('sha') if isinstance(tree, dict) else None
        if not isinstance(commit_sha, str) or not isinstance(tree_sha, str):
            raise ValueError(f'invalid arknights npc commit response for {ref}')
        return commit_sha, tree_sha

    async def tree(self, tree_sha: str) -> dict[str, SourceFile]:
        data = await self.request(f'{self.api_url}/git/trees/{quote(tree_sha, safe="")}?recursive=1', 'tree')
        assert isinstance(data, dict)
        if data.get('truncated'):
            raise RuntimeError('arknights npc source tree is truncated')
        entries = data.get('tree')
        if not isinstance(entries, list):
            raise ValueError('invalid arknights npc tree response')
        return build_source_files(entries)

    def load_state(self) -> str | None:
        if not self.source_state_path.exists():
            return None
        try:
            data = json.loads(self.source_state_path.read_text(encoding='utf-8'))
        except json.JSONDecodeError as error:
            raise ValueError(f'invalid npc source state {self.source_state_path}') from error
        commit_sha = data.get('commit') if isinstance(data, dict) else None
        return commit_sha if isinstance(commit_sha, str) else None

    def save_state(self, commit_sha: str) -> None:
        self.source_state_path.parent.mkdir(exist_ok=True)
        self.source_state_path.write_text(
            json.dumps({'commit': commit_sha}, indent=2) + '\n',
            encoding='utf-8',
        )

    async def upload_file(self, commit_sha: str, file: SourceFile, semaphore: asyncio.Semaphore) -> None:
        assert self.upload is not None
        async with semaphore:
            source_url = self.raw_url % (commit_sha, quote(file.source_path, safe='/'))
            content = await self.request(source_url, file.source_path, byte=True)
            assert isinstance(content, bytes)
            await self.upload(file.target_path, content)
            print(f'upload arknights npc {file.target_path}')

    def commit_state(self, commit_sha: str) -> None:
        subprocess.run(['git', 'add', str(self.source_state_path)], check=True)
        subprocess.run(
            ['git', 'commit', '-m', f'[Arknights NPC UPDATE] Source:{get_time()}-{commit_sha[:6]}'],
            check=True,
        )
        github_env = os.environ.get('GITHUB_ENV')
        if github_env:
            with open(github_env, mode='a', encoding='utf-8') as file:
                file.write('update=1\n')

    async def run(self) -> None:
        async with aiohttp.ClientSession() as client:
            self.client = client
            self.upload = Uploader(client)
            current_commit, current_tree_sha = await self.commit('main')
            previous_commit = self.load_state()

            current_files = await self.tree(current_tree_sha)
            previous_files: dict[str, SourceFile] = {}
            if previous_commit:
                _, previous_tree_sha = await self.commit(previous_commit)
                previous_files = await self.tree(previous_tree_sha)

            updates = changed_files(previous_files, current_files)
            if updates:
                print(f'update arknights npc {current_commit} ({len(updates)} files)')
                semaphore = asyncio.Semaphore(self.concurrency)
                await asyncio.gather(*[
                    self.upload_file(current_commit, file, semaphore)
                    for file in updates
                ])
            else:
                print(f'pass arknights npc {current_commit}')

            if previous_commit != current_commit:
                self.save_state(current_commit)
                self.commit_state(current_commit)

    def start(self) -> None:
        asyncio.run(self.run())


ArknightsNPCResource = ArknightsNPCSource()
