import re
from nltk.stem import WordNetLemmatizer
from nltk.tokenize import wordpunct_tokenize
from nltk.corpus import wordnet as wn
from nltk import pos_tag
from experimental_unixcoder.bug_localization import BugLocalization

class Preprocessor:
    def __init__(self):
        self.bug_localizer = BugLocalization()

    def camel_case_split(identifier):
        """
        Splits camelCase words via regular expression

        Args:
            identifier (string): token to be matched

        Returns:
            list: split tokens
        """

        matches = re.finditer('.+?(?:(?<=[a-z])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])|$)', identifier)
        return [m.group(0) for m in matches]
    
    def tokenize_text(text):
        """
        Tokenizes the text into individual words
        Splits camelCase words
        Removes cases

        Args:
            text (string): string to be tokenized

        Returns:
            list: tokens
        """

        tokens = []

        # Tokenize the input text
        for token in wordpunct_tokenize(text):
            for word in Preprocessor.camel_case_split(token):
                tokens.append(word)

        return tokens
    
    def remove_special_characters(text):
        """
        Removes special characters and punctuation from input text

        Args:
            text (string): string to have special chars removed 

        Returns:
            text (string): new string with special chars removed
        """
        
        # Replace escape character with a ' '
        text = text.replace("\n", " ")

        # Replace special characters and numbers with a ' '
        text = re.sub("[^A-Za-z\s]+", " ", text)
        return text
    
    def get_pos_tag(token):
        """
        Gets the WordNet POS tag (i.e. ADJ, NOUN, VERB, ADV) of a token 

        Args:
            token (string): token to be tagged

        Returns:
            WordNet tag constant (i.e. wn.NOUN -> 'n')
        """
        
        # Get the POS tag from the pos_tag function
        # pos_tag returns a tuple so we index [0][1] to return the tag of a single token
        tag = pos_tag([token])[0][1]

        if tag.startswith('JJ'):
            return wn.ADJ
        elif tag.startswith('NN'):
            return wn.NOUN
        elif tag.startswith('VB'):
            return wn.VERB
        elif tag.startswith('RB'):
            return wn.ADV
        # If no matches, default to noun
        else:
            return wn.NOUN
        
    def lemmatize_tokens(tokens):
        '''
        Lemmatizes a list of tokens with their POS tag

        Args:
            tokens (list of strings): tokens to be lemmatized
        
        Returns:
            tokens (list of strings): lemmatized tokens
        '''
        lemmatizer = WordNetLemmatizer()

        # Call the get_pos_tag function to assign the correct POS tag to each token in tokens
        return [lemmatizer.lemmatize(token, Preprocessor.get_pos_tag(token)) for token in tokens]        
    
    def preprocess_text(self, text, stop_words_path):
        """
        Preprocesses input text by
            - Removing Numbers
            - Removing special characters
            - Removing punctuation
            - Removing tokens of size 1-2
            - Removing cases
            - Removing inputted stop words

        Args:
            text (string): text to be preprocessed
            stop_words (string): path to a stop words file

        Returns:
            string: preprocessed text
        """

        # Remove all special chars and punctuation from the text
        text = Preprocessor.remove_special_characters(text)

        # Tokenize the text
        tokens = Preprocessor.tokenize_text(text)

        try:
            # Read stop words from the input
            with open(stop_words_path) as f:
                stop_words = set(f.read().splitlines())
        except FileNotFoundError:
            print(f"Error: The stop words at '{stop_words_path}' were not found.")
            return

        # Remove stop words
        tokens = [token for token in tokens if token not in stop_words]

        # Remove cases
        tokens = [token.lower() for token in tokens]

        # Lemmatize the tokens. i.e., running -> run
        tokens = Preprocessor.lemmatize_tokens(tokens)
        
        # Remove short tokens
        tokens = [token for token in tokens if len(token) > 2]

        # Join the tokens into a single string and remove cases
        preprocessed_text = " ".join(tokens)

        print(preprocessed_text)

        # Calculate embeddings for preprocessed text
        preprocessed_text = self.bug_localizer.encode_text(preprocessed_text)

        return preprocessed_text