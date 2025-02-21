import pytest
from utils.preprocess import Preprocessor
from nltk.corpus import wordnet as wn

def test_camel_case_split():
    # Test camel case splitting
    assert Preprocessor.camel_case_split("camelCaseWord") == ["camel", "Case", "Word"]
    assert Preprocessor.camel_case_split("HTMLParser") == ["HTML", "Parser"]
    assert Preprocessor.camel_case_split("simple") == ["simple"]


def test_tokenize_text():
    # Test tokenization with camel case splitting
    tokens = Preprocessor.tokenize_text("A quickSample for tokenizing CamelCaseWords.")
    assert tokens == ["A", "quick", "Sample", "for", "tokenizing", "Camel", "Case", "Words", "."]

    # Edge case: check empty string
    assert Preprocessor.tokenize_text("") == []


def test_remove_special_characters():
    # Test special characters and numbers removal
    result = Preprocessor.remove_special_characters("Hello, World! 123.")
    assert result == "Hello  World   "

    # Edge case: empty string
    assert Preprocessor.remove_special_characters("") == ""

    # Edge case: string with only special characters
    assert Preprocessor.remove_special_characters("!@#$%^&*()") == " "


def test_get_pos_tag():
    # Test POS tag mapping
    # assert Preprocessor.get_pos_tag("beautiful") == wn.ADJ
    assert Preprocessor.get_pos_tag("run") == wn.VERB
    assert Preprocessor.get_pos_tag("quickly") == wn.ADV
    assert Preprocessor.get_pos_tag("dog") == wn.NOUN

    # Edge case: unknown or rare word
    assert Preprocessor.get_pos_tag("xyzzy") == wn.NOUN  # Defaults to NOUN


def test_lemmatize_tokens():
    # Test lemmatization
    tokens = ["running", "dogs", "beautifully", "was"]
    lemmatized = Preprocessor.lemmatize_tokens(tokens)
    assert lemmatized == ["run", "dog", "beautifully", "be"]
