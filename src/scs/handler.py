from concurrent.futures.thread import ThreadPoolExecutor
from concurrent.futures import Future, as_completed
from typing import List, Iterable, Tuple, Optional

from .constraint import SyntaxConstraint
from .constraint.json import valid_json, force_json_schema
from .constraint.one_of import one_of


def _check_token_batched(
    check: SyntaxConstraint,
    check_idx: int,
    token_batch: List[str],
    start_token_idx: int,
) -> Iterable[Tuple[int, int]]:
    for token_idx, token in enumerate(token_batch, start=start_token_idx):
        if not check.check_next(token):
            print('MULTIPROCESSING')
            yield check_idx, token_idx


class SyntaxValidityCheckFactory:

    def __init__(self, **init_kwargs):
        self._init_kwargs = init_kwargs

    def __call__(self) -> SyntaxConstraint:
        raise NotImplementedError()


class JSONValidityCheckFactory(SyntaxValidityCheckFactory):
     
     def __call__(self) -> SyntaxConstraint:
         return valid_json(**self._init_kwargs)
     

class JSONSchemaCheckFactory(SyntaxValidityCheckFactory):

    def __call__(self) -> SyntaxConstraint:
        return force_json_schema(**self._init_kwargs)


class OneOfValidityCheckFactory(SyntaxValidityCheckFactory):

    def __call__(self) -> SyntaxConstraint:
        return one_of(**self._init_kwargs)


class SyntaxValidityCheckHandler:

    def __init__(
        self,
        token_vocab: List[str],
        check_factory: SyntaxValidityCheckFactory,
        num_workers: int = 2,
        begin_first_check: bool = True,
    ):
        self._executor = ThreadPoolExecutor(max_workers=num_workers)
        self._num_workers = num_workers
        self._batch_size = len(token_vocab) // num_workers
        self._active_futures: List[Future] = []
        self._initialized = False
        self._token_vocab = token_vocab
        self._check_factory = check_factory
        self._active_checks = [check_factory()]  # initialize single check to constrain start tokens
        if begin_first_check:
            self.process_invalid_next_tokens()

    def cancel_current_check(self):
        for future in self._active_futures:
            future.cancel()
        self._active_futures = []

    r"""
    Returns tuples (batch idx, vocab idx) for every invalid next token for each active check.
    Should be called after each update."""
    def process_invalid_next_tokens(self):
        self._active_futures = []
        for check_idx, check in enumerate(self._active_checks):
            for start_token_idx in range(0, len(self._token_vocab), self._batch_size):
                print('ADDING BATCH TO THREAD')
                self._active_futures += [
                    self._executor.submit(
                        _check_token_batched,
                        check,
                        check_idx,
                        self._token_vocab[start_token_idx:start_token_idx+self._batch_size],
                        start_token_idx,
                    )
                ]

    def await_invalid_next_tokens(self) -> Iterable[Tuple[int, int]]:
        for future in as_completed(self._active_futures):
            invalid_token_batch = future.result()
            yield from invalid_token_batch
        self._active_futures = []

    r"""
    Updates parsers for all active checks with next sampled token for the corresponding generation.
    If this is the first sample step, initialize a check for each element in batch"""
    def update(self, next_token_ids: List[int], begin_next_check: bool = True):
        next_token_id = next_token_ids[0]  # currently only supports single-beam and greedy
        print(next_token_id)
        print(f"Next token: {next_token_id}, {repr(self._token_vocab[next_token_id])}")
        if not self._initialized:  # this is the first sampling step
            self._active_checks += [self._check_factory() for _ in range(len(next_token_ids) - 1)]
        for token_id, check in zip(next_token_ids, self._active_checks):
            check.update_parser(self._token_vocab[token_id])
        if begin_next_check:
            self.process_invalid_next_tokens()
