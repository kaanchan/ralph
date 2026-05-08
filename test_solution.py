from solution import fibonacci

def test_fibonacci_zero():
    assert fibonacci(0) == 0

def test_fibonacci_one():
    assert fibonacci(1) == 1

def test_fibonacci_two():
    assert fibonacci(2) == 1

def test_fibonacci_three():
    assert fibonacci(3) == 2

def test_fibonacci_ten():
    assert fibonacci(10) == 55
