import pytest

from pySerialTransfer.CRC import CRC
from io import StringIO
import sys


def test_crc_init():
    """Test the initialization of the CRC class."""
    crc = CRC()
    assert crc.poly == 0x9B
    assert crc.crc_len == 8
    assert crc.table_len == 256
    assert len(crc.cs_table) == 256


def test_crc_poly():
    """Test the initialization of the CRC class with a custom polynomial."""
    polynomial = 0x8C
    crc = CRC(polynomial)
    assert crc.poly == polynomial & 0xFF
    assert crc.crc_len == 8
    assert crc.table_len == 256
    assert len(crc.cs_table) == 256


#  Note: The CRC class has no upper limit on the crc_len parameter, but attempting to use a value greater than 32 hangs
#  the test. The CRC class should be updated to handle this case.
@pytest.mark.parametrize('crc_len', [4, 8, 16])    
def test_custom_positive_crc_len(crc_len):
    """Test the initialization of the CRC class with a custom crc length."""
    expected_table_len = pow(2, crc_len)
    crc = CRC(crc_len=crc_len)
    assert crc.table_len == expected_table_len
    assert len(crc.cs_table) == expected_table_len


def test_crc_calculate():
    """Test the calculate method of the CRC class returns an integer."""
    crc = CRC()
    result = crc.calculate([0x31])
    assert isinstance(result, int)


def test_calculate_with_int_list_no_dist():
    crc_instance = CRC()
    arr = [0x31, 0x32, 0x33, 0x34, 0x35]
    expected_output = 218
    result = crc_instance.calculate(arr)
    assert result == expected_output


def test_calculate_with_int_list_with_dist():
    crc_instance = CRC()
    arr = [0x31, 0x32, 0x33, 0x34, 0x35]
    dist = 3
    expected_output = 209
    result = crc_instance.calculate(arr, dist)
    assert result == expected_output


def test_calculate_with_char_list_no_dist():
    crc_instance = CRC()
    arr = ["1", "2", "3", "4", "5"]
    expected_output = 128
    result = crc_instance.calculate(arr)
    assert result == expected_output


def test_calculate_with_char_list_with_dist():
    crc_instance = CRC()
    arr = ["1", "2", "3", "4", "5"]
    dist = 3
    expected_output = 68
    result = crc_instance.calculate(arr, dist)
    assert result == expected_output


def test_calculate_with_int_no_dist():
    crc_instance = CRC()
    arr = 0x31
    expected_output = 205
    result = crc_instance.calculate(arr)
    assert result == expected_output


def test_calculate_with_non_int_no_dist():
    crc_instance = CRC()
    arr = ["a", "b", "c", "d", "e"]
    expected_output = 52
    result = crc_instance.calculate(arr)
    assert result == expected_output
    

def test_calculate_with_non_int_with_dist():
    crc_instance = CRC()
    arr = ["a", "b", "c", "d", "e"]
    dist = 3
    expected_output = 245
    result = crc_instance.calculate(arr, dist)
    assert result == expected_output


# TODO: Handle this case in the calculate method   
@pytest.mark.xfail(reason="not currently handled in the calculate method")   
def test_calculate_with_dist_greater_than_list_length():
    crc_instance = CRC()
    arr = [0x31, 0x32, 0x33, 0x34, 0x35]
    dist = 10
    expected_output = 218
    result = crc_instance.calculate(arr, dist)
    assert result == expected_output


def test_print_table():
    """Test the print_table method of the CRC class."""
    # Create an instance of CRC
    crc_instance = CRC()

    # Redirect stdout to a buffer
    stdout = sys.stdout
    sys.stdout = StringIO()

    # Call the method
    crc_instance.print_table()

    # Get the output and restore stdout
    output = sys.stdout.getvalue()
    sys.stdout = stdout

    # Prepare the expected output
    expected_output = ""
    for i in range(len(crc_instance.cs_table)):
        expected_output += hex(crc_instance.cs_table[i]).upper().replace('X', 'x')
        if (i + 1) % 16:
            expected_output += " "
        else:
            expected_output += "\n"

    # Assert that the output matches the expected output
    assert output == expected_output
    

def test_calculate_with_empty_list():
    """Test that the calculate method returns 0 when an empty list is passed."""
    crc_instance = CRC()
    arr = []
    result = crc_instance.calculate(arr)
    assert result == 0


# TODO: Handle this case in the calculate method   
@pytest.mark.xfail(reason="not currently handled in the calculate method") 
def test_calculate_with_negative_dist():
    """Test that the calculate method raises a ValueError when the dist parameter is negative."""
    crc_instance = CRC()
    arr = [0x31, 0x32, 0x33, 0x34, 0x35]
    dist = -1
    with pytest.raises(ValueError):
        crc_instance.calculate(arr, dist)

        
def test_calculate_with_string_input():
    """Test that the calculate method can handle a string input."""
    crc_instance = CRC()
    arr = "abc"
    result = crc_instance.calculate(arr)
    assert result == 245


def test_calculate_with_list_of_mixed_types():
    """Test that the calculate method can handle a list of mixed types."""
    crc_instance = CRC()
    arr = [0x31, "a", 0x33, "b", 0x35]
    result = crc_instance.calculate(arr)
    assert result == 254
