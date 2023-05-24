from concurrent.futures.thread import ThreadPoolExecutor
from concurrent.futures import Future, as_completed
from typing import List, Iterable, Tuple, Optional, Dict, Type
from dataclasses import dataclass
import numpy as np

from .constraint import SyntaxConstraint
from .constraint.json import valid_json, force_json_schema
from .constraint.one_of import one_of
from .incremental_parse.json.parser import NonNumericTokenGroup, InvalidFloatTokenGroup, BeginWithNonJsonCharGroup, NoQuoteCharGroup, NumericTokenGroup
from .incremental_parse.string_match import NonAlnumGroup
from .incremental_parse import TokenGroup, AllTokenGroup, EmptyTokenGroup


TOKEN_GROUPS = [
    AllTokenGroup, EmptyTokenGroup, NonNumericTokenGroup, InvalidFloatTokenGroup, BeginWithNonJsonCharGroup, NonAlnumGroup, NoQuoteCharGroup, NumericTokenGroup
]


def make_vocab_splits(vocab: List[str], *token_group_types: Type[TokenGroup]) -> Dict[Type, "VocabSplit"]:
    split_dict = {}
    for T in token_group_types:
        split = VocabSplit()
        split.filter_vocab(vocab, grouping=T)
        split_dict[T] = split
    return split_dict


def _check_token_batched(
    check: SyntaxConstraint,
    check_idx: int,
    token_batch: List[Tuple[int, str]],
) -> Iterable[Tuple[int, int]]:
    for token_idx, token in token_batch:
        if not check.check_next(token):
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
        self._vocab_splits = make_vocab_splits(token_vocab, *TOKEN_GROUPS)
        self._check_factory = check_factory
        self._active_checks = [check_factory()]  # initialize single check to constrain start tokens
        if begin_first_check:
            self.process_invalid_next_tokens()

    r"""
    Yield tokens from each invalid group"""
    def await_invalid_next_tokens(self) -> Iterable[Tuple[int, int]]:
        for check_idx, check in enumerate(self._active_checks):
            toks_to_check = np.ones(len(self._token_vocab)).astype(np.bool_)
            suppress_tokens, allow_tokens = [], []
            invalid_vocab_split = self._vocab_splits.get(check.invalid_token_group())
            if invalid_vocab_split:
                suppress_tokens = invalid_vocab_split.filtered
            for token_id, token in suppress_tokens:
                yield check_idx, token_id
                toks_to_check[token_id] = False
            valid_vocab_split = self._vocab_splits.get(check.valid_token_group())
            if valid_vocab_split:
                allow_tokens = valid_vocab_split.filtered
            for token_id, token in allow_tokens:
                toks_to_check[token_id] = False
            for token_id in np.where(toks_to_check)[0]:
                token = self._token_vocab[token_id]
                if not check.check_next(token):
                    yield check_idx, token_id

    def process_invalid_next_tokens(self):
        pass

    def cancel_current_check(self):
        for future in self._active_futures:
            future.cancel()
        self._active_futures = []

    # r"""
    # Returns tuples (batch idx, vocab idx) for every invalid next ungrouped token ocurringfor each active check.
    # Should be called after each update."""
    # def process_invalid_next_tokens(self):
    #     self._active_futures = []
    #     for check_idx, check in enumerate(self._active_checks):
    #         for start_token_idx in range(0, len(self._ungrouped_tokens), self._batch_size):
    #             self._active_futures += [
    #                 self._executor.submit(
    #                     _check_token_batched,
    #                     check,
    #                     check_idx,
    #                     self._ungrouped_tokens[start_token_idx:start_token_idx+self._batch_size],
    #                 )
    #             ]

    # def await_invalid_next_tokens(self) -> Iterable[Tuple[int, int]]:
    #     yield from self._invalid_tokens_from_group()
    #     for future in as_completed(self._active_futures):
    #         invalid_token_batch = future.result()
    #         yield from invalid_token_batch
    #     self._active_futures = []

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


class VocabSplit:
    
    def __init__(self) -> None:
        self.filtered = []
        self.remaining = []

    def filter_vocab(self, vocab: List[str], grouping: Type[TokenGroup]):
        self.filtered = []
        self.remaining = []
        for i, tok in enumerate(vocab):
            if isinstance(tok, str) and grouping.filter(tok):
                self.filtered += [(i, tok)]
            else:
                self.remaining += [(i, tok)]
