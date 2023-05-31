# Syntactically Constrained Sampling for Language Models
[](https://youtu.be/nCXio16A7ms)

## Enforce Syntax Constraints on LLM Output!

Large Language Models (LLMs) have seen adoption and integration into a variety of pipelines to extract and stuctured data and even act autonomously through projects such as [LangChain](https://github.com/hwchase17/langchain) and [AutoGPT](https://github.com/Significant-Gravitas/Auto-GPT). In such use cases, success of the system depends on the LLM's output adhereing to a specific format or syntax, eg. JSON. While LLMs can follow formatting instructions provided in their prompts, deviation can occur (especially for complex formatting instructions) leading to failure when the output is parsed.

This project explores guided LM sampling under syntax constraints allowing user-defined syntax constraints to be enforced during token sampling and guaranteeing adherence to this syntax in the final generated text.

**Currently only supports greedy and single-beam sampling.**

## Example Notebooks

- [Explore currently supported constraints with Vicuna-13B in oobabooga's text-generation web UI](https://colab.research.google.com/github/IsaacRe/Syntactically-Constrained-Sampling/blob/main/notebooks/Sampling_Constraints_Web_UI_vicuna_13b_GPTQ_4bit_128g.ipynb)
- [Test applying syntax constraints to non-instruction-finetuned LM's](https://colab.research.google.com/github/IsaacRe/Syntactically-Constrained-Sampling/blob/main/notebooks/Examples_with_Non_IFT_Models.ipynb)
- [Walkthrough of developing and applying a new syntax constraint](https://colab.research.google.com/github/IsaacRe/Syntactically-Constrained-Sampling/blob/main/notebooks/Adding_a_New_Constraint.ipynb)

## Local Setup

Install our fork of [🤗 transformers](https://github.com/IsaacRe/transformers):
```bash
pip install git+https://github.com/IsaacRe/transformers@syntactically-constrained-sampling
```
Either

- Install the most recent version of this repo:
    ```bash
    pip install git+https://github.com/IsaacRe/Syntactically-Constrained-Sampling
    ```
- Or build and install local version
    ```bash
    python -m build && pip install dist/sampling-constraints-<VERSION>.tar.gz
    ```

Try out some of the constraints below:

## Currently Supported Constraints
Have an idea for a useful constraint? Open an issue!

### JSON Schema
Force LM output to follow a specific JSON object, defined in typescript(ish) notation:
```python
from transformers.pipelines import pipeline

schema = """
{
    output: string,
    array_output: []number,
    optional_output?: number,
    nested_schema: []{
        inner_output: string
    }
}
"""

pipe = pipeline(model='gpt2')
output = pipe('Input', enforce_json_schema=schema)
```
Example output:
```json
{
    "output": "some text",
    "array_output": [1, 2, 3],
    "nested_schema": [
        {"inner_output": "more text"},
        {"inner_output": "even more text"}
    ]
}
```

### One Of

Force LLM to select from a particular set of outputs

```python
from transformers.pipelines import pipeline

options = 'Option A,Option B'

pipe = pipeline(model='gpt2')
output = pipe('Input', enforce_one_of=options)
```

Example output:
```
Option A
```

## How it works

### Incremental Parsers
The current approach relies on an `IncrementalParser` class to periodically check validity of sampled sequences under its particular syntax constraint. Inheriting classes must implement the following methods:

```python
append(self, chars: str) -> None:
```
- append `chars` to the string being parsed and continue parsing
- raise `ParseFailure` if deviation from expected format

```python
copy(self) -> IncrementalParser
```
- return copy of the parser and its internal state

Parsing a sequence can be carried out by making subsequent calls to `append`, each time passing a new token to append to the string being parsed. Validity of a sequence after a new token is appended can be checked by creating a copy of the current parser then calling its `append` method with the candidate token and checking if a `ParseFailure` is raised.

### Constrained Sampling
Using this fork of [🤗 transformers]() we hook into the generation loop and enforce syntax constraints defined via an `IncrementalParser` before each sampling step. For each token in the tokenizer's vocabulary it checks whether a `ParseFailure` is raised when appending it to a copy of the current parse state. Once the LM's forward pass completes logits corresponding to next tokens that caused a `ParseFailure` are suppressed (effectively removed from the distribution of tokens that may be sampled).

## Optimizations

### Token Groups

Iterating over all tokens in a LM's vocab is expensive. To save time we can use `TokenGroup`'s to include or exclude sets of tokens from sampling during each generation step, without having to check continued syntax validity for each token in that set.

`TokenGroup` classes must implement the static `filter` method:

```python
filter(token: str) -> bool
```

- returns whether the passed token is a member of this group

Incremental Parsers can leverage Token Groups by implementing the following methods:

```python
valid_token_group(self) -> Type[TokenGroup]
```
- returns a `TokenGroup` class defining a subset of tokens allowed to be sampled next

```python
invalid_token_group(self) -> Type[TokenGroup]
```

- returns a `TokenGroup` class defining a subset of tokens **not** allowed to be sampled next

The check handler will filter the tokenizer vocab into groups before generation begins and will call the above methods to check for valid/invalid token groups before checking per-token validity. If present, tokens in the invalid token group will be suppressed. Remaining tokens not present in either valid/invalid groups are then checked for syntax validity.

### Forcing Specific Tokens
There may be times during parsing when a particular character or sequence of characters are required to maintain syntax validity. An `IncrementalParser` can implement `get_next` to skip token validity checks when this is the case:

```python
get_next(self) -> List[str]
```
- returns exhaustive list of valid next sequences to constrain generation, or empty list ot leave generation unconstrained

The check handler evaluates the result of `get_next` before all other checks. If one or more results are returned, one token prefixing each result will be allowed and all other tokens will be suppressed, otherwise checks continue.
