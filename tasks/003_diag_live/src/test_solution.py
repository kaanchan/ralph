from solution import is_palindrome

def test_empty_string():
    assert is_palindrome("") == True

def test_single_character():
    assert is_palindrome("a") == True

def test_two_characters_same():
    assert is_palindrome("aa") == True

def test_two_characters_different():
    assert is_palindrome("ab") == False

def test_palindrome_with_spaces():
    assert is_palindrome("A man a plan a canal Panama") == True

def test_non_palindrome_with_spaces():
    assert is_palindrome("Hello World") == False

def test_palindrome_ignore_case():
    assert is_palindrome("Racecar") == True

def test_non_palindrome_ignore_case():
    assert is_palindrome("Python") == False
