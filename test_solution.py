from solution import fibonacci

def test_fibonacci():
    assert fibonacci(1) == 0
    assert fibonacci(2) == 1
    assert fibonacci(3) == 1
    assert fibonacci(4) == 2
    assert fibonacci(5) == 3
    assert fibonacci(6) == 5
    assert fibonacci(7) == 8
    assert fibonacci(8) == 13
    assert fibonacci(9) == 21
    assert fibonacci(10) == 34

def test_fibonacci_invalid():
    import pytest
    with pytest.raises(ValueError, match="n must be a positive integer"):
        fibonacci(0)
    with pytest.raises(ValueError, match="n must be a positive integer"):
        fibonacci(-5)
