from solution import explain_meaning_of_life

def test_explain_meaning_of_life():
    # Arrange
    expected = "The meaning of life is a philosophical question concerning the significance and purpose of human existence."

    # Act
    result = explain_meaning_of_life()

    # Assert
    assert result == expected
