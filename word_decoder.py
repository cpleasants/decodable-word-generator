from enum import Enum, auto
import utils

class Indicator(Enum):
    SHORT_VOWEL = auto()
    LONG_VOWEL = auto()
    HARD_CONSONANT = auto()
    SOFT_CONSONANT = auto()
    LETTER_COMBO = auto()
    SILENT_E = auto()
    UNDECODABLE = auto()

SOUND_CATEGORIES = {
    Indicator.SHORT_VOWEL: utils.short_vowels,
    Indicator.LONG_VOWEL: utils.long_vowels,
    Indicator.HARD_CONSONANT: utils.hard_consonants,
    Indicator.SOFT_CONSONANT: utils.soft_consonants,
}

class WordDecoder:
    def __init__(self, word: str):
        """Initialize with a word and prepare processing state."""
        self.word = word.lower()
        if self.word not in utils.simplified_cmudict:
            raise Exception("Word not found")

        self.word_phonemes = utils.simplified_cmudict[self.word]
        self.remaining_letters = self.word
        self.remaining_sounds = self.word_phonemes
        self.letter_parts:list = []
        self.sound_parts:list = []
        self.indicators:list[Indicator] = []
        self.decodable = True
        self.decode()

    def handle_undecodable(self):
        """Mark remaining letters as undecodable and halt processing."""
        self.decodable = False
        self.letter_parts.append(self.remaining_letters)
        self.sound_parts.append(tuple(self.remaining_sounds))
        self.indicators.append(Indicator.UNDECODABLE)
        self.remaining_letters = ''
        self.remaining_sounds = []

    def process_affixes(self, affixes_dict, is_prefix=True):
        """Process prefixes and suffixes and update state accordingly."""
        affix_letter_parts = []
        affix_sound_parts = []
        affix_indicators = []

        for affix, affix_sounds in affixes_dict.items():
            affix_letters = affix.replace('-', '')
            letters_match = self.word.startswith(affix_letters) if is_prefix else self.word.endswith(affix_letters)
            for affix_sound in affix_sounds:
                sounds_match = tuple(self.word_phonemes[ : len(affix_sound)]) == affix_sound if is_prefix else tuple(self.word_phonemes[-len(affix_sound) : ]) == affix_sound
                num_sounds = len(affix_sound)
                if letters_match and sounds_match:
                    affix_letter_parts.append(affix)
                    affix_sound_parts.append(affix_sound)
                    affix_indicators.append(Indicator.LETTER_COMBO)
                    self.remaining_letters = self.remaining_letters.lstrip(affix_letters) if is_prefix else self.remaining_letters.rstrip(affix_letters)
                    self.remaining_sounds = self.remaining_sounds[num_sounds:] if is_prefix else self.remaining_sounds[ : -num_sounds]
                    break
        return affix_letter_parts, affix_sound_parts, affix_indicators
        

    def process_single_letter_sound(self, letter, sound, indicator):
        """Process a single letter with its corresponding sound."""
        self.letter_parts.append(letter)
        self.sound_parts.append(sound)
        self.indicators.append(indicator)
        self.remaining_letters = self.remaining_letters[1:]
        self.remaining_sounds = self.remaining_sounds[len(sound) : ] if self.remaining_sounds else []

    def decode(self):
        """Main decoding function that applies all processing logic."""

        # Process prefixes and suffixes
        prefix_letter_parts, prefix_sound_parts, prefix_indicators = self.process_affixes(utils.prefixes)
        suffix_letters, suffix_sound_parts, suffix_indicators = self.process_affixes(utils.suffixes, is_prefix = False)

        # Process through the remaining_letters:
        while len(self.remaining_letters) > 0:
            # first search through all letter combinations
            for letters, sounds in utils.letter_combinations.items():
                for sound in sounds:
                    if self.remaining_letters.startswith(letters) and tuple(self.remaining_sounds[:len(sound)]) == sound:
                        self.letter_parts.append(letters)
                        self.sound_parts.append(sound)
                        self.indicators.append(Indicator.LETTER_COMBO)
                        self.remaining_letters = self.remaining_letters.lstrip(letters)
                        self.remaining_sounds = self.remaining_sounds[len(sound) : ]
                        break
                else:
                    # Continue searching other letter combinations if no match is found
                    continue
                # If the inner break is hit, break the outer loop as well
                break
            # Some words contain punctuation (e.g. "won't") -- skip the punctuation
            else:
                this_letter = self.remaining_letters[0]
                if not this_letter.isalpha():
                    self.remaining_letters = self.remaining_letters[1:]
                    continue

                matched = False

                # Silent E
                if (len(self.remaining_sounds) == 0 or self.remaining_sounds[0] not in utils.all_vowel_sounds) and this_letter == 'e':
                    self.process_single_letter_sound(this_letter, '', Indicator.SILENT_E)
                    matched = True
                
                for indicator, sound_dict in SOUND_CATEGORIES.items():
                    for sound in sound_dict.get(this_letter, []):
                        if tuple(self.remaining_sounds[:len(sound)]) == sound:
                            self.process_single_letter_sound(this_letter, sound, indicator)
                            matched = True
                            break
                    if matched:
                        break
                    
                if not matched:
                    self.handle_undecodable()
                
        # Add back in the suffixes
        self.letter_parts = prefix_letter_parts + self.letter_parts + suffix_letters
        self.sound_parts = prefix_sound_parts + self.sound_parts + suffix_sound_parts
        self.indicators = prefix_indicators + self.indicators + suffix_indicators

        self._decoded = {
            'letter_parts' : self.letter_parts, 
            'indicators' : self.indicators ,
            'sound_parts' : self.sound_parts,
            'decodable' : self.decodable
        }
    
    @property
    def decoded(self):
        return self._decoded
    
    def is_vc(self, word: str, allowed_blends_and_digraphs=None, include_long_vowels=False):
        """
        Determines if a given word follows the "VC" (vowel-consonant) pattern.

        A valid VC word must:
        - Contain exactly two phonetic sounds: one vowel followed by one consonant.
        - Only include short vowels unless `include_long_vowels` is set to True.
        - Have a valid consonant ending, either a single consonant or one listed in `allowed_blends_and_digraphs`.

        Parameters:
            word (str): The word to check.
            allowed_blends_and_digraphs (list, optional): A list of allowed consonant blends or digraphs. Defaults to an empty list.
            include_long_vowels (bool, optional): Whether to allow long vowels. Defaults to False.

        Returns:
            bool: True if the word follows the VC pattern, False otherwise.

        Raises:
            Exception: If the word contains more than one vowel.
        """
        if allowed_blends_and_digraphs is None:
            allowed_blends_and_digraphs = []

        sounds = utils.simplified_cmudict[word]

        # Ensure the word has exactly two phonetic sounds: a vowel followed by a consonant
        if len(sounds) != 2 or not is_vowel_sound(sounds[0]) or is_vowel_sound(sounds[1]):
            return False

        # If long vowels shouldn't be included, verify the vowel is short
        if not include_long_vowels and not only_short_vowels(word):
            return False

        # Extract consonant part of the word
        consonant_part = word[1:]

        # Ensure no additional vowels exist beyond the first letter
        if any(is_vowel(letter) for letter in consonant_part):
            raise Exception(f"The word '{word}' appears to have more than one vowel!")

        # Check if the consonant part is a single letter or an allowed blend/digraph
        return len(consonant_part) == 1 or consonant_part in allowed_blends_and_digraphs
        
    def is_cvc(self, word:str, allowed_blends_and_digraphs=None, include_long_vowels=False):
        """
        Determines if a given word follows the "CVC" (consonant-vowel-consonant) pattern.

        A valid CVC word must:
        - Contain one consonant (or blend) followed by one vowel followed by one consonant (or blend).
        - Only include short vowels unless `include_long_vowels` is set to True.
        - Consonant sounds must be a single letter or one listed in `allowed_blends_and_digraphs`.

        Parameters:
            word (str): The word to check.
            allowed_blends_and_digraphs (list, optional): A list of allowed consonant blends or digraphs. Defaults to an empty list.
            include_long_vowels (bool, optional): Whether to allow long vowels. Defaults to False.

        Returns:
            bool: True if the word follows the CVC pattern, False otherwise.

        Raises:
            Exception: If the word contains more than one vowel sound.
        """
        if allowed_blends_and_digraphs is None:
            allowed_blends_and_digraphs = []

        sounds = utils.simplified_cmudict[word]

        # Ensure the word has exactly two phonetic sounds: a vowel followed by a consonant
        if len(sounds) != 2 or not is_vowel_sound(sounds[0]) or is_vowel_sound(sounds[1]):
            return False

        # If long vowels shouldn't be included, verify the vowel is short
        if not include_long_vowels and not only_short_vowels(word):
            return False

        # Extract consonant part of the word
        consonant_part = word[1:]

        # Ensure no additional vowels exist beyond the first letter
        if any(is_vowel(letter) for letter in consonant_part):
            raise Exception(f"The word '{word}' appears to have more than one vowel!")

        # Check if the consonant part is a single letter or an allowed blend/digraph
        return len(consonant_part) == 1 or consonant_part in allowed_blends_and_digraphs
        return len(word) == 3 and not is_vowel(word[0]) and is_vowel(word[1]) and not is_vowel(word[2])