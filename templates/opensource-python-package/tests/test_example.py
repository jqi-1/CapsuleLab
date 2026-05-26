from my_package import hello
from my_package.example import add


def test_hello():
    assert hello() == "Hello from my-package!"


def test_add():
    assert add(2, 3) == 5
