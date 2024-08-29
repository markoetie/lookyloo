#!/usr/bin/env python3

from __future__ import annotations

import logging
import logging.config
from pathlib import Path

from redis import Redis

from lookyloo import Indexing
from lookyloo.default import AbstractManager, get_config, get_socket_path


logging.config.dictConfig(get_config('logging'))


class BackgroundIndexer(AbstractManager):

    def __init__(self, full: bool=False, loglevel: int | None=None):
        super().__init__(loglevel)
        self.is_public_instance = get_config('generic', 'public_instance')
        self.full_indexer = full
        self.indexing = Indexing(full_index=self.full_indexer)
        if self.full_indexer:
            self.script_name = 'background_full_indexer'
        else:
            self.script_name = 'background_indexer'

        # Redis connector so we don't use the one from Lookyloo
        self.redis = Redis(unix_socket_path=get_socket_path('cache'), decode_responses=True)

    def _to_run_forever(self) -> None:
        self._check_indexes()

    def _check_indexes(self) -> None:
        if not self.indexing.can_index():
            # There is no reason to run this method in multiple scripts.
            self.logger.info('Indexing already ongoing in another process.')
            return None
        self.logger.info(f'Check {self.script_name}...')
        # NOTE: only get the non-archived captures for now.
        for uuid, d in self.redis.hscan_iter('lookup_dirs'):
            if not self.full_indexer:
                # If we're not running the full indexer, check if the capture should be indexed.
                if self.is_public_instance and self.redis.hexists(d, 'no_index'):
                    # Capture unindexed
                    continue

            self.indexing.index_capture(uuid, Path(d))
        self.indexing.indexing_done()
        self.logger.info('... done.')


def main() -> None:
    i = BackgroundIndexer()
    i.run(sleep_in_sec=60)


def main_full_indexer() -> None:
    if not get_config('generic', 'index_everything'):
        raise Exception('Full indexer is disabled.')
    # NOTE: for now, it only indexes the captures that aren't archived.
    #       we will change that later, but for now, it's a good start.
    i = BackgroundIndexer(full=True)
    i.run(sleep_in_sec=60)


if __name__ == '__main__':
    main()
