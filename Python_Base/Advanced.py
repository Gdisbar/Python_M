"""
Python Advanced Concepts
=================================

Comprehensive guide covering:
- Lambda expressions
- Generators and iterators
- Map, filter, and functional programming
- Dunder methods (magic methods)
- Functools module

"""

import functools
import operator
import itertools
import time
import sys
from collections.abc import Iterator, Iterable
from typing import Any, Callable, Generator, TypeVar


# =============================================================================
# 1. LAMBDA EXPRESSIONS - ADVANCED PATTERNS
# =============================================================================

print("=" * 60)
print("1. LAMBDA EXPRESSIONS - ADVANCED PATTERNS")
print("=" * 60)

def lambda_basics():
    print("\n--- Lambda Fundamentals ---")
    
    # Basic syntax comparison
    def square_func(x):
        return x ** 2
    
    square_lambda = lambda x: x ** 2
    
    print(f"Function: {square_func(5)}")
    print(f"Lambda: {square_lambda(5)}")
    
    # Multiple arguments
    add = lambda x, y: x + y
    multiply = lambda x, y, z=1: x * y * z
    
    print(f"Add: {add(3, 4)}")
    print(f"Multiply: {multiply(2, 3, 4)}")

def lambda_advanced_patterns():
    print("\n--- Advanced Lambda Patterns ---")
    
    # 1. Lambda with conditionals
    max_lambda = lambda a, b: a if a > b else b
    sign = lambda x: 1 if x > 0 else -1 if x < 0 else 0
    
    print(f"Max: {max_lambda(10, 5)}")
    print(f"Sign of -3: {sign(-3)}")
    
    # 2. Lambda for key functions in sorting
    students = [
        {'name': 'Alice', 'grade': 85, 'age': 20},
        {'name': 'Bob', 'grade': 90, 'age': 19},
        {'name': 'Charlie', 'grade': 78, 'age': 21}
    ]
    
    # Sort by grade (descending)
    by_grade = sorted(students, key=lambda s: s['grade'], reverse=True)
    print("Sorted by grade:", [s['name'] for s in by_grade])
    
    # Sort by multiple criteria
    by_age_then_grade = sorted(students, key=lambda s: (s['age'], -s['grade']))
    print("Sorted by age then grade:", [s['name'] for s in by_age_then_grade])
    
    # 3. Lambda in data processing
    data = [(1, 'a'), (2, 'b'), (3, 'c'), (4, 'd')]
    
    # Extract and transform
    numbers = list(map(lambda item: item[0] * 2, data))
    letters = list(map(lambda item: item[1].upper(), data))
    
    print(f"Doubled numbers: {numbers}")
    print(f"Upper letters: {letters}")
    
    # 4. Lambda closures (capturing variables)
    def create_multiplier(n):
        return lambda x: x * n
    
    double = create_multiplier(2)
    triple = create_multiplier(3)
    
    print(f"Double 5: {double(5)}")
    print(f"Triple 5: {triple(5)}")
    
    # 5. Lambda with complex data structures
    nested_data = [
        {'users': [{'score': 95}, {'score': 87}]},
        {'users': [{'score': 92}, {'score': 88}]},
    ]
    
    # Extract maximum scores
    max_scores = list(map(
        lambda group: max(user['score'] for user in group['users']), 
        nested_data
    ))
    print(f"Max scores per group: {max_scores}")

def lambda_gotchas():
    print("\n--- Lambda Gotchas and Limitations ---")
    
    # 1. Late binding closure problem
    funcs = []
    for i in range(3):
        # WRONG: All lambdas will use i=2
        funcs.append(lambda x: x * i)
    
    print("Wrong closure results:")
    for func in funcs:
        print(f"  {func(10)}")  # All will be 20 (10 * 2)
    
    # CORRECT: Capture i in default argument
    funcs_correct = []
    for i in range(3):
        funcs_correct.append(lambda x, multiplier=i: x * multiplier)
    
    print("Correct closure results:")
    for func in funcs_correct:
        print(f"  {func(10)}")  # 0, 10, 20
    
    # 2. Lambda limitations
    print("\nLambda limitations:")
    print("- No statements (only expressions)")
    print("- No annotations in older Python versions")
    print("- Limited debugging (shows as <lambda>)")
    print("- Should be simple - complex logic should use def")


# =============================================================================
# 2. GENERATORS - COMPREHENSIVE GUIDE
# =============================================================================

print("\n" + "=" * 60)
print("2. GENERATORS - COMPREHENSIVE GUIDE")
print("=" * 60)

def basic_generators():
    print("\n--- Generator Basics ---")
    
    # Generator function
    def countdown(n):
        print(f"Starting countdown from {n}")
        while n > 0:
            yield n
            n -= 1
        print("Countdown finished!")
    
    # Generator is lazy - nothing happens until iteration
    gen = countdown(3)
    print(f"Generator object: {gen}")
    
    # Iterate through generator
    for num in gen:
        print(f"Count: {num}")
    
    # Generator expression
    squares = (x**2 for x in range(5))
    print(f"Generator expression: {squares}")
    print(f"Squares: {list(squares)}")

def advanced_generators():
    print("\n--- Advanced Generator Patterns ---")
    
    # 1. Infinite generators
    def fibonacci():
        a, b = 0, 1
        while True:
            yield a
            a, b = b, a + b
    
    fib = fibonacci()
    first_10_fib = [next(fib) for _ in range(10)]
    print(f"First 10 Fibonacci: {first_10_fib}")
    
    # 2. Generator with state
    def running_average():
        total = 0
        count = 0
        while True:
            value = yield total / count if count > 0 else 0
            if value is not None:
                total += value
                count += 1
    
    avg_gen = running_average()
    next(avg_gen)  # Prime the generator
    
    print("Running average:")
    for val in [10, 20, 30]:
        result = avg_gen.send(val)
        print(f"  Added {val}, average: {result:.2f}")
    
    # 3. Generator pipeline
    def read_data():
        """Simulate reading data"""
        data = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
        for item in data:
            print(f"Reading: {item}")
            yield item
    
    def filter_even(data_gen):
        """Filter even numbers"""
        for item in data_gen:
            if item % 2 == 0:
                print(f"Filtering: {item} (even)")
                yield item
    
    def square(data_gen):
        """Square the numbers"""
        for item in data_gen:
            result = item ** 2
            print(f"Squaring: {item} -> {result}")
            yield result
    
    # Create pipeline
    pipeline = square(filter_even(read_data()))
    print("Pipeline results:", list(pipeline))
    
    # 4. Generator with cleanup
    def file_processor(filename):
        print(f"Opening {filename}")
        try:
            # Simulate file processing
            for i in range(3):
                yield f"Line {i} from {filename}"
        finally:
            print(f"Closing {filename}")
    
    processor = file_processor("data.txt")
    for line in processor:
        print(f"Processing: {line}")

def generator_expressions_advanced():
    print("\n--- Advanced Generator Expressions ---")
    
    # Nested generator expressions
    matrix = [[1, 2, 3], [4, 5, 6], [7, 8, 9]]
    
    # Flatten matrix
    flattened = (item for row in matrix for item in row)
    print(f"Flattened: {list(flattened)}")
    
    # Conditional generator expressions
    even_squares = (x**2 for x in range(10) if x % 2 == 0)
    print(f"Even squares: {list(even_squares)}")
    
    # Generator expressions with functions
    def process(x):
        return x * 2 + 1
    
    processed = (process(x) for x in range(5))
    print(f"Processed: {list(processed)}")
    
    # Memory efficiency demonstration
    print("\n--- Memory Efficiency ---")
    
    # List comprehension - creates full list in memory
    list_comp = [x**2 for x in range(1000000)]
    print(f"List size: {sys.getsizeof(list_comp)} bytes")
    
    # Generator - minimal memory
    gen_exp = (x**2 for x in range(1000000))
    print(f"Generator size: {sys.getsizeof(gen_exp)} bytes")
    
    # del list_comp  # Free memory

def generator_methods():
    print("\n--- Generator Methods: send(), throw(), close() ---")
    
    def responsive_generator():
        print("Generator started")
        value = None
        try:
            while True:
                if value is None:
                    received = yield "Ready for input"
                else:
                    received = yield f"Processed: {value}"
                
                if received is not None:
                    value = received
        except GeneratorExit:
            print("Generator closing...")
        except Exception as e:
            print(f"Generator error: {e}")
            yield f"Error handled: {e}"
    
    gen = responsive_generator()
    
    # Start generator
    print(next(gen))
    
    # Send values
    print(gen.send(42))
    print(gen.send(100))
    
    # Throw exception
    try:
        print(gen.throw(ValueError("Test error")))
    except StopIteration:
        pass
    
    # Close generator
    gen = responsive_generator()
    next(gen)
    gen.close()


# =============================================================================
# 3. ITERATORS - CUSTOM IMPLEMENTATIONS
# =============================================================================

print("\n" + "=" * 60)
print("3. ITERATORS - CUSTOM IMPLEMENTATIONS")
print("=" * 60)

class CountDown:
    """Custom iterator for countdown"""
    
    def __init__(self, start):
        self.start = start
        self.current = start
    
    def __iter__(self):
        return self
    
    def __next__(self):
        if self.current <= 0:
            raise StopIteration
        
        self.current -= 1
        return self.current + 1

class InfiniteRange:
    """Infinite range iterator with step"""
    
    def __init__(self, start=0, step=1):
        self.current = start
        self.step = step
    
    def __iter__(self):
        return self
    
    def __next__(self):
        result = self.current
        self.current += self.step
        return result

class ChainedIterator:
    """Chain multiple iterables together"""
    
    def __init__(self, *iterables):
        self.iterables = iterables
        self.current_iter = 0
        self.current_iterator = iter(iterables[0]) if iterables else iter([])
    
    def __iter__(self):
        return self
    
    def __next__(self):
        try:
            return next(self.current_iterator)
        except StopIteration:
            self.current_iter += 1
            if self.current_iter >= len(self.iterables):
                raise StopIteration
            self.current_iterator = iter(self.iterables[self.current_iter])
            return next(self.current_iterator)

def iterator_examples():
    print("\n--- Custom Iterator Examples ---")
    
    # CountDown iterator
    countdown = CountDown(5)
    print("Countdown:", list(countdown))
    
    # Infinite range (take only first 10)
    inf_range = InfiniteRange(10, 3)
    first_10 = [next(inf_range) for _ in range(10)]
    print("Infinite range (step 3):", first_10)
    
    # Chained iterator
    chained = ChainedIterator([1, 2, 3], ['a', 'b'], [10, 20])
    print("Chained:", list(chained))

class SmartRange:
    """Range with additional features"""
    
    def __init__(self, *args):
        if len(args) == 1:
            self.start, self.stop, self.step = 0, args[0], 1
        elif len(args) == 2:
            self.start, self.stop, self.step = args[0], args[1], 1
        elif len(args) == 3:
            self.start, self.stop, self.step = args
        else:
            raise ValueError("SmartRange takes 1-3 arguments")
    
    def __iter__(self):
        current = self.start
        if self.step > 0:
            while current < self.stop:
                yield current
                current += self.step
        else:
            while current > self.stop:
                yield current
                current += self.step
    
    def __len__(self):
        if self.step > 0:
            return max(0, (self.stop - self.start + self.step - 1) // self.step)
        else:
            return max(0, (self.start - self.stop - self.step - 1) // (-self.step))
    
    def __getitem__(self, index):
        if isinstance(index, slice):
            # Handle slicing
            start, stop, step = index.indices(len(self))
            return SmartRange(
                self.start + start * self.step,
                self.start + stop * self.step,
                self.step * step
            )
        else:
            # Handle indexing
            if index < 0:
                index += len(self)
            if 0 <= index < len(self):
                return self.start + index * self.step
            raise IndexError("SmartRange index out of range")
    
    def __contains__(self, value):
        if self.step > 0:
            return (self.start <= value < self.stop and 
                   (value - self.start) % self.step == 0)
        else:
            return (self.stop < value <= self.start and 
                   (self.start - value) % (-self.step) == 0)
    
    def __repr__(self):
        return f"SmartRange({self.start}, {self.stop}, {self.step})"

def smart_range_demo():
    print("\n--- Smart Range Demo ---")
    
    sr = SmartRange(0, 20, 3)
    print(f"SmartRange: {sr}")
    print(f"Length: {len(sr)}")
    print(f"Items: {list(sr)}")
    print(f"Item at index 2: {sr[2]}")
    print(f"Slice [1:4]: {list(sr[1:4])}")
    print(f"Contains 6: {6 in sr}")
    print(f"Contains 7: {7 in sr}")


# =============================================================================
# 4. MAP, FILTER, AND FUNCTIONAL PROGRAMMING
# =============================================================================

print("\n" + "=" * 60)
print("4. MAP, FILTER, AND FUNCTIONAL PROGRAMMING")
print("=" * 60)

def map_advanced():
    print("\n--- Advanced Map Usage ---")
    
    # Basic map
    numbers = [1, 2, 3, 4, 5]
    squared = list(map(lambda x: x**2, numbers))
    print(f"Squared: {squared}")
    
    # Map with multiple iterables
    nums1 = [1, 2, 3]
    nums2 = [4, 5, 6]
    nums3 = [7, 8, 9]
    
    # Add three numbers together
    sums = list(map(lambda x, y, z: x + y + z, nums1, nums2, nums3))
    print(f"Triple sum: {sums}")
    
    # Map with different length iterables (stops at shortest)
    short = [1, 2]
    long_list = [10, 20, 30, 40]
    products = list(map(lambda x, y: x * y, short, long_list))
    print(f"Products: {products}")
    
    # Map with built-in functions
    strings = ['123', '456', '789']
    integers = list(map(int, strings))
    print(f"String to int: {integers}")
    
    # Map with custom functions
    def analyze_string(s):
        return {
            'length': len(s),
            'upper': s.upper(),
            'first_char': s[0] if s else None
        }
    
    words = ['hello', 'world', 'python']
    analyzed = list(map(analyze_string, words))
    print("String analysis:")
    for analysis in analyzed:
        print(f"  {analysis}")
    
    # Map with class methods
    class NumberProcessor:
        def __init__(self, multiplier):
            self.multiplier = multiplier
        
        def process(self, x):
            return x * self.multiplier + 1
    
    processor = NumberProcessor(3)
    processed = list(map(processor.process, [1, 2, 3, 4]))
    print(f"Processed: {processed}")

def filter_advanced():
    print("\n--- Advanced Filter Usage ---")
    
    # Basic filtering
    numbers = range(1, 21)
    evens = list(filter(lambda x: x % 2 == 0, numbers))
    print(f"Even numbers: {evens}")
    
    # Filter with None (removes falsy values)
    mixed_data = [1, 0, 'hello', '', None, [], [1, 2], False, True]
    truthy = list(filter(None, mixed_data))
    print(f"Truthy values: {truthy}")
    
    # Complex filtering
    students = [
        {'name': 'Alice', 'grade': 85, 'subjects': ['math', 'science']},
        {'name': 'Bob', 'grade': 92, 'subjects': ['math', 'english']},
        {'name': 'Charlie', 'grade': 78, 'subjects': ['science', 'art']},
        {'name': 'Diana', 'grade': 96, 'subjects': ['math', 'science', 'english']}
    ]
    
    # Students with grade > 80 and taking math
    good_math_students = list(filter(
        lambda s: s['grade'] > 80 and 'math' in s['subjects'],
        students
    ))
    print("Good math students:")
    for student in good_math_students:
        print(f"  {student['name']}: {student['grade']}")
    
    # Filter with custom predicate functions
    def is_prime(n):
        if n < 2:
            return False
        for i in range(2, int(n**0.5) + 1):
            if n % i == 0:
                return False
        return True
    
    numbers = range(1, 30)
    primes = list(filter(is_prime, numbers))
    print(f"Prime numbers: {primes}")
    
    # Filter with regex
    import re
    
    emails = [
        'user@example.com',
        'invalid-email',
        'test@test.org',
        'another@domain.co.uk',
        'not_an_email'
    ]
    
    email_pattern = re.compile(r'^[^@]+@[^@]+\.[^@]+$')
    valid_emails = list(filter(email_pattern.match, emails))
    print(f"Valid emails: {valid_emails}")

def functional_programming_patterns():
    print("\n--- Functional Programming Patterns ---")
    
    # Combining map and filter
    numbers = range(1, 11)
    
    # Get squares of even numbers
    even_squares = list(map(lambda x: x**2, filter(lambda x: x % 2 == 0, numbers)))
    print(f"Even squares: {even_squares}")
    
    # Using itertools for advanced patterns
    from itertools import takewhile, dropwhile, accumulate
    
    # takewhile - take elements while condition is true
    data = [1, 3, 5, 8, 9, 11, 4, 6]
    odds_until_even = list(takewhile(lambda x: x % 2 != 0, data))
    print(f"Odds until first even: {odds_until_even}")
    
    # dropwhile - drop elements while condition is true
    after_first_even = list(dropwhile(lambda x: x % 2 != 0, data))
    print(f"After first even: {after_first_even}")
    
    # accumulate - running totals/operations
    numbers = [1, 2, 3, 4, 5]
    running_sum = list(accumulate(numbers))
    running_product = list(accumulate(numbers, operator.mul))
    print(f"Running sum: {running_sum}")
    print(f"Running product: {running_product}")
    
    # Function composition
    def compose(*functions):
        return functools.reduce(lambda f, g: lambda x: f(g(x)), functions, lambda x: x)
    
    # Create composed function
    add_one = lambda x: x + 1
    double = lambda x: x * 2
    square = lambda x: x ** 2
    
    composed = compose(square, double, add_one)
    result = composed(3)  # ((3 + 1) * 2) ** 2 = 64
    print(f"Composed function result: {result}")

def performance_comparison():
    print("\n--- Performance Comparison ---")
    
    data = list(range(100000))
    
    # List comprehension vs map
    start = time.time()
    list_comp = [x**2 for x in data if x % 2 == 0]
    list_comp_time = time.time() - start
    
    start = time.time()
    map_filter = list(map(lambda x: x**2, filter(lambda x: x % 2 == 0, data)))
    map_filter_time = time.time() - start
    
    print(f"List comprehension time: {list_comp_time:.4f}s")
    print(f"Map/filter time: {map_filter_time:.4f}s")
    print(f"Ratio: {map_filter_time / list_comp_time:.2f}x")
    
    # Generator vs list
    start = time.time()
    gen_result = (x**2 for x in data if x % 2 == 0)
    # Just creating the generator
    gen_create_time = time.time() - start
    
    start = time.time()
    # Consuming the generator
    consumed = sum(gen_result)
    gen_consume_time = time.time() - start
    
    print(f"Generator creation time: {gen_create_time:.6f}s")
    print(f"Generator consumption time: {gen_consume_time:.4f}s")


# =============================================================================
# 5. DUNDER METHODS (MAGIC METHODS)
# =============================================================================

print("\n" + "=" * 60)
print("5. DUNDER METHODS (MAGIC METHODS)")
print("=" * 60)

class Vector:
    """Comprehensive vector class demonstrating dunder methods"""
    
    def __init__(self, *components):
        self.components = list(components)
    
    # String representation
    def __repr__(self):
        return f"Vector({', '.join(map(str, self.components))})"
    
    def __str__(self):
        return f"<{', '.join(map(str, self.components))}>"
    
    # Arithmetic operations
    def __add__(self, other):
        if isinstance(other, Vector):
            if len(self.components) != len(other.components):
                raise ValueError("Vector dimensions must match")
            return Vector(*(a + b for a, b in zip(self.components, other.components)))
        elif isinstance(other, (int, float)):
            return Vector(*(c + other for c in self.components))
        return NotImplemented
    
    def __radd__(self, other):
        return self.__add__(other)
    
    def __sub__(self, other):
        if isinstance(other, Vector):
            if len(self.components) != len(other.components):
                raise ValueError("Vector dimensions must match")
            return Vector(*(a - b for a, b in zip(self.components, other.components)))
        elif isinstance(other, (int, float)):
            return Vector(*(c - other for c in self.components))
        return NotImplemented
    
    def __mul__(self, other):
        if isinstance(other, (int, float)):
            return Vector(*(c * other for c in self.components))
        elif isinstance(other, Vector):
            # Dot product
            if len(self.components) != len(other.components):
                raise ValueError("Vector dimensions must match")
            return sum(a * b for a, b in zip(self.components, other.components))
        return NotImplemented
    
    def __rmul__(self, other):
        return self.__mul__(other)
    
    def __truediv__(self, other):
        if isinstance(other, (int, float)):
            if other == 0:
                raise ZeroDivisionError("Cannot divide by zero")
            return Vector(*(c / other for c in self.components))
        return NotImplemented
    
    # Comparison operations
    def __eq__(self, other):
        if isinstance(other, Vector):
            return self.components == other.components
        return False
    
    def __ne__(self, other):
        return not self.__eq__(other)
    
    def __lt__(self, other):
        if isinstance(other, Vector):
            return self.magnitude() < other.magnitude()
        return NotImplemented
    
    def __le__(self, other):
        return self.__lt__(other) or self.__eq__(other)
    
    def __gt__(self, other):
        if isinstance(other, Vector):
            return self.magnitude() > other.magnitude()
        return NotImplemented
    
    def __ge__(self, other):
        return self.__gt__(other) or self.__eq__(other)
    
    # Container operations
    def __len__(self):
        return len(self.components)
    
    def __getitem__(self, index):
        return self.components[index]
    
    def __setitem__(self, index, value):
        self.components[index] = value
    
    def __contains__(self, value):
        return value in self.components
    
    def __iter__(self):
        return iter(self.components)
    
    # Hash and bool
    def __hash__(self):
        return hash(tuple(self.components))
    
    def __bool__(self):
        return any(c != 0 for c in self.components)
    
    # Call method
    def __call__(self, func):
        """Apply function to all components"""
        return Vector(*(func(c) for c in self.components))
    
    # Context manager
    def __enter__(self):
        print(f"Entering vector context: {self}")
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        print(f"Exiting vector context: {self}")
        return False
    
    # Utility methods
    def magnitude(self):
        return sum(c**2 for c in self.components) ** 0.5
    
    def normalize(self):
        mag = self.magnitude()
        if mag == 0:
            raise ValueError("Cannot normalize zero vector")
        return self / mag

def dunder_methods_demo():
    print("\n--- Dunder Methods Demo ---")
    
    # Create vectors
    v1 = Vector(3, 4)
    v2 = Vector(1, 2)
    v3 = Vector(3, 4)
    
    print(f"v1: {v1}")
    print(f"v2: {v2}")
    print(f"repr(v1): {repr(v1)}")
    
    # Arithmetic
    print(f"v1 + v2 = {v1 + v2}")
    print(f"v1 - v2 = {v1 - v2}")
    print(f"v1 * 2 = {v1 * 2}")
    print(f"3 * v1 = {3 * v1}")
    print(f"v1 • v2 = {v1 * v2}")  # Dot product
    print(f"v1 / 2 = {v1 / 2}")
    
    # Comparison
    print(f"v1 == v3: {v1 == v3}")
    print(f"v1 > v2: {v1 > v2}")
    print(f"v1 < v2: {v1 < v2}")
    
    # Container operations
    print(f"len(v1): {len(v1)}")
    print(f"v1[0]: {v1[0]}")
    print(f"3 in v1: {3 in v1}")
    print(f"List of components: {list(v1)}")
    
    # Boolean and hash
    print(f"bool(v1): {bool(v1)}")
    print(f"bool(Vector(0, 0)): {bool(Vector(0, 0))}")
    print(f"hash(v1): {hash(v1)}")
    
    # Call method
    squared_v1 = v1(lambda x: x**2)
    print(f"v1 squared: {squared_v1}")
    
    # Context manager
    with v1 as vector:
        print(f"Inside context: magnitude = {vector.magnitude():.2f}")

class SmartDict(dict):
    """Dictionary with additional features"""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.access_count = {}
    
    def __getitem__(self, key):
        self.access_count[key] = self.access_count.get(key, 0) + 1
        return super().__getitem__(key)
    
    def __setitem__(self, key, value):
        if key in self:
            print(f"Updating existing key: {key}")
        super().__setitem__(key, value)
    
    def __delitem__(self, key):
        if key in self.access_count:
            del self.access_count[key]
        super().__delitem__(key)
    
    def __missing__(self, key):
        """Called when key is not found"""
        print(f"Key '{key}' not found, returning default")
        return f"default_for_{key}"
    
    def get_stats(self):
        return dict(self.access_count)
    
    # Custom attribute access
    def __getattr__(self, name):
        if name.startswith('get_'):
            key = name[4:]  # Remove 'get_' prefix
            return lambda: self.get(key, f"No value for {key}")
        raise AttributeError(f"'{type(self).__name__}' object has no attribute '{name}'")

class AttrDict:
    """Dictionary-like access via attributes"""
    
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)
    
    def __getattr__(self, name):
        try:
            return self.__dict__[name]
        except KeyError:
            raise AttributeError(f"'{type(self).__name__}' object has no attribute '{name}'")
    
    def __setattr__(self, name, value):
        self.__dict__[name] = value
    
    def __delattr__(self, name):
        try:
            del self.__dict__[name]
        except KeyError:
            raise AttributeError(f"'{type(self).__name__}' object has no attribute '{name}'")
    
    def __repr__(self):
        items = ', '.join(f'{k}={v!r}' for k, v in self.__dict__.items())
        return f'{type(self).__name__}({items})'

def advanced_dunder_demo():
    print("\n--- Advanced Dunder Methods ---")
    
    # SmartDict demo
    smart = SmartDict(a=1, b=2, c=3)
    print(f"SmartDict: {smart}")
    
    # Access items (tracked)
    print(f"smart['a']: {smart['a']}")
    print(f"smart['a']: {smart['a']}")  # Access again
    print(f"smart['b']: {smart['b']}")
    
    # Missing key
    print(f"smart['missing']: {smart['missing']}")
    
    # Dynamic attribute access
    print(f"smart.get_a(): {smart.get_a()}")
    print(f"smart.get_nonexistent(): {smart.get_nonexistent()}")
    
    # Statistics
    print(f"Access stats: {smart.get_stats()}")
    
    # AttrDict demo
    config = AttrDict(host='localhost', port=8080, debug=True)
    print(f"Config: {config}")
    print(f"Host: {config.host}")
    print(f"Port: {config.port}")
    
    config.timeout = 30
    print(f"Updated config: {config}")

class Singleton:
    """Singleton pattern using dunder methods"""
    _instances = {}
    
    def __new__(cls, *args, **kwargs):
        if cls not in cls._instances:
            cls._instances[cls] = super().__new__(cls)
        return cls._instances[cls]
    
    def __init__(self, name="default"):
        if not hasattr(self, 'initialized'):
            self.name = name
            self.initialized = True

class ImmutablePoint:
    """Immutable point class"""
    
    def __init__(self, x, y):
        object.__setattr__(self, 'x', x)
        object.__setattr__(self, 'y', y)
    
    def __setattr__(self, name, value):
        raise AttributeError("ImmutablePoint is immutable")
    
    def __delattr__(self, name):
        raise AttributeError("ImmutablePoint is immutable")
    
    def __repr__(self):
        return f"ImmutablePoint({self.x}, {self.y})"
    
    def __hash__(self):
        return hash((self.x, self.y))

def special_dunder_patterns():
    print("\n--- Special Dunder Patterns ---")
    
    # Singleton pattern
    s1 = Singleton("first")
    s2 = Singleton("second")
    print(f"s1 is s2: {s1 is s2}")
    print(f"s1.name: {s1.name}")  # Will be "first"
    
    # Immutable objects
    point = ImmutablePoint(3, 4)
    print(f"Point: {point}")
    print(f"Hash: {hash(point)}")
    
    try:
        point.x = 5  # This will raise an error
    except AttributeError as e:
        print(f"Error: {e}")


# =============================================================================
# 6. FUNCTOOLS MODULE - COMPREHENSIVE GUIDE
# =============================================================================

print("\n" + "=" * 60)
print("6. FUNCTOOLS MODULE - COMPREHENSIVE GUIDE")
print("=" * 60)

def functools_basics():
    print("\n--- Functools Basics ---")
    
    # 1. partial - partial function application
    from functools import partial
    
    def multiply(x, y, z):
        return x * y * z
    
    # Create specialized functions
    double = partial(multiply, 2)  # x=2, need y and z
    triple_by_five = partial(multiply, 3, 5)  # x=3, y=5, need z
    
    print(f"double(3, 4): {double(3, 4)}")  # 2 * 3 * 4 = 24
    print(f"triple_by_five(2): {triple_by_five(2)}")  # 3 * 5 * 2 = 30
    
    # Partial with keyword arguments
    def greet(greeting, name, punctuation="!"):
        return f"{greeting}, {name}{punctuation}"
    
    say_hello = partial(greet, "Hello")
    polite_greet = partial(greet, punctuation=".")
    
    print(f"say_hello('Alice'): {say_hello('Alice')}")
    print(f"polite_greet('Good morning', 'Bob'): {polite_greet('Good morning', 'Bob')}")
    
    # 2. wraps - preserving function metadata
    from functools import wraps
    
    def timing_decorator(func):
        @wraps(func)  # Preserves func's metadata
        def wrapper(*args, **kwargs):
            start = time.time()
            result = func(*args, **kwargs)
            end = time.time()
            print(f"{func.__name__} took {end - start:.4f}s")
            return result
        return wrapper
    
    @timing_decorator
    def slow_function():
        """A slow function for demonstration"""
        time.sleep(0.1)
        return "Done"
    
    result = slow_function()
    print(f"Function name: {slow_function.__name__}")
    print(f"Function doc: {slow_function.__doc__}")

def functools_advanced():
    print("\n--- Advanced Functools ---")
    
    # 1. lru_cache - memoization
    from functools import lru_cache
    
    @lru_cache(maxsize=128)
    def fibonacci(n):
        if n < 2:
            return n
        return fibonacci(n-1) + fibonacci(n-2)
    
    # Without cache, fib(30) would be very slow
    print(f"fibonacci(30): {fibonacci(30)}")
    print(f"Cache info: {fibonacci.cache_info()}")
    
    # Custom cache example
    @lru_cache(maxsize=None)  # Unlimited cache
    def expensive_operation(x, y):
        print(f"Computing expensive operation for {x}, {y}")
        time.sleep(0.1)  # Simulate expensive computation
        return x ** y + y ** x
    
    # First call - slow
    result1 = expensive_operation(2, 3)
    # Second call with same args - fast (cached)
    result2 = expensive_operation(2, 3)
    print(f"Results: {result1}, {result2}")
    
    # 2. singledispatch - generic functions
    from functools import singledispatch
    
    @singledispatch
    def process(arg):
        print(f"Processing generic object: {arg}")
    
    @process.register(int)
    def _(arg):
        print(f"Processing integer: {arg ** 2}")
    
    @process.register(str)
    def _(arg):
        print(f"Processing string: {arg.upper()}")
    
    @process.register(list)
    def _(arg):
        print(f"Processing list: {sorted(arg)}")
    
    # Demonstrate polymorphic behavior
    process(42)
    process("hello")
    process([3, 1, 4, 1, 5])
    process(3.14)  # Falls back to generic
    
    # 3. reduce - fold operation
    from functools import reduce
    
    numbers = [1, 2, 3, 4, 5]
    
    # Sum using reduce
    total = reduce(lambda x, y: x + y, numbers)
    print(f"Sum: {total}")
    
    # Product using reduce
    product = reduce(lambda x, y: x * y, numbers)
    print(f"Product: {product}")
    
    # Find maximum
    maximum = reduce(lambda x, y: x if x > y else y, numbers)
    print(f"Maximum: {maximum}")
    
    # Complex reduce example - flatten nested lists
    nested = [[1, 2], [3, 4], [5, 6]]
    flattened = reduce(lambda acc, lst: acc + lst, nested, [])
    print(f"Flattened: {flattened}")
    
    # Reduce with operator functions
    import operator
    sum_op = reduce(operator.add, numbers)
    product_op = reduce(operator.mul, numbers)
    print(f"Sum (operator): {sum_op}")
    print(f"Product (operator): {product_op}")

def decorator_patterns():
    print("\n--- Advanced Decorator Patterns ---")
    
    # 1. Parameterized decorators
    def retry(max_attempts=3, delay=1):
        def decorator(func):
            @wraps(func)
            def wrapper(*args, **kwargs):
                for attempt in range(max_attempts):
                    try:
                        return func(*args, **kwargs)
                    except Exception as e:
                        if attempt == max_attempts - 1:
                            raise
                        print(f"Attempt {attempt + 1} failed: {e}")
                        time.sleep(delay)
            return wrapper
        return decorator
    
    @retry(max_attempts=3, delay=0.1)
    def unreliable_function(success_rate=0.3):
        import random
        if random.random() < success_rate:
            return "Success!"
        raise Exception("Random failure")
    
    try:
        result = unreliable_function(0.7)
        print(f"Result: {result}")
    except Exception as e:
        print(f"Final failure: {e}")
    
    # 2. Class-based decorators
    class CountCalls:
        def __init__(self, func):
            self.func = func
            self.count = 0
            functools.update_wrapper(self, func)
        
        def __call__(self, *args, **kwargs):
            self.count += 1
            print(f"Call #{self.count} to {self.func.__name__}")
            return self.func(*args, **kwargs)
    
    @CountCalls
    def say_hello(name):
        return f"Hello, {name}!"
    
    print(say_hello("Alice"))
    print(say_hello("Bob"))
    print(f"Total calls: {say_hello.count}")
    
    # 3. Property decorators with functools
    class Circle:
        def __init__(self, radius):
            self._radius = radius
            self._area = None
            self._circumference = None
        
        @property
        def radius(self):
            return self._radius
        
        @radius.setter
        def radius(self, value):
            if value < 0:
                raise ValueError("Radius cannot be negative")
            self._radius = value
            # Clear cached values
            self._area = None
            self._circumference = None
        
        @property
        @lru_cache(maxsize=1)
        def area(self):
            print("Calculating area...")
            import math
            return math.pi * self._radius ** 2
        
        @property
        @lru_cache(maxsize=1)
        def circumference(self):
            print("Calculating circumference...")
            import math
            return 2 * math.pi * self._radius
    
    circle = Circle(5)
    print(f"Area: {circle.area}")  # Calculated
    print(f"Area: {circle.area}")  # Cached
    print(f"Circumference: {circle.circumference}")

def functional_composition():
    print("\n--- Functional Composition ---")
    
    # 1. Function composition with reduce
    def compose(*functions):
        return reduce(lambda f, g: lambda x: f(g(x)), functions, lambda x: x)
    
    # Create simple functions
    add_one = lambda x: x + 1
    multiply_by_two = lambda x: x * 2
    square = lambda x: x ** 2
    
    # Compose functions
    pipeline = compose(square, multiply_by_two, add_one)
    result = pipeline(3)  # ((3 + 1) * 2) ** 2 = 64
    print(f"Composed result: {result}")
    
    # 2. Pipe operator simulation
    class Pipe:
        def __init__(self, value):
            self.value = value
        
        def __or__(self, func):
            return Pipe(func(self.value))
        
        def __repr__(self):
            return f"Pipe({self.value})"
    
    # Usage: value | func1 | func2 | func3
    result = Pipe(3) | add_one | multiply_by_two | square
    print(f"Pipe result: {result}")
    
    # 3. Currying with partial
    def curry(func):
        @wraps(func)
        def curried(*args, **kwargs):
            if len(args) + len(kwargs) >= func.__code__.co_argcount:
                return func(*args, **kwargs)
            return partial(func, *args, **kwargs)
        return curried
    
    @curry
    def add_three(x, y, z):
        return x + y + z
    
    # Can be called with any number of arguments
    print(f"add_three(1, 2, 3): {add_three(1, 2, 3)}")
    print(f"add_three(1)(2)(3): {add_three(1)(2)(3)}")
    print(f"add_three(1, 2)(3): {add_three(1, 2)(3)}")

def caching_strategies():
    print("\n--- Advanced Caching Strategies ---")
    
    # 1. Custom cache with TTL (Time To Live)
    import time
    from collections import defaultdict
    
    def ttl_cache(ttl_seconds=60):
        def decorator(func):
            cache = {}
            timestamps = {}
            
            @wraps(func)
            def wrapper(*args, **kwargs):
                key = str(args) + str(sorted(kwargs.items()))
                current_time = time.time()
                
                # Check if cached and not expired
                if (key in cache and 
                    key in timestamps and 
                    current_time - timestamps[key] < ttl_seconds):
                    print(f"Cache hit for {func.__name__}")
                    return cache[key]
                
                # Compute and cache
                print(f"Cache miss for {func.__name__}")
                result = func(*args, **kwargs)
                cache[key] = result
                timestamps[key] = current_time
                return result
            
            wrapper.cache_clear = lambda: (cache.clear(), timestamps.clear())
            wrapper.cache_info = lambda: {'size': len(cache)}
            return wrapper
        return decorator
    
    @ttl_cache(ttl_seconds=2)
    def fetch_data(url):
        print(f"Fetching data from {url}")
        time.sleep(0.1)  # Simulate network delay
        return f"Data from {url}"
    
    # Test TTL cache
    print(fetch_data("http://api.example.com"))  # Cache miss
    print(fetch_data("http://api.example.com"))  # Cache hit
    time.sleep(2.1)  # Wait for TTL to expire
    print(fetch_data("http://api.example.com"))  # Cache miss again
    
    # 2. Memoization with custom key function
    def memoize_with_key(key_func=None):
        def decorator(func):
            cache = {}
            
            @wraps(func)
            def wrapper(*args, **kwargs):
                if key_func:
                    cache_key = key_func(*args, **kwargs)
                else:
                    cache_key = str(args) + str(sorted(kwargs.items()))
                
                if cache_key not in cache:
                    cache[cache_key] = func(*args, **kwargs)
                return cache[cache_key]
            
            wrapper.cache = cache
            wrapper.cache_clear = cache.clear
            return wrapper
        return decorator
    
    # Custom key function that ignores certain parameters
    @memoize_with_key(key_func=lambda x, y, debug=False: f"{x}-{y}")
    def compute(x, y, debug=False):
        if debug:
            print(f"Computing {x} + {y}")
        return x + y
    
    print(f"compute(1, 2): {compute(1, 2)}")
    print(f"compute(1, 2, debug=True): {compute(1, 2, debug=True)}")  # Same cache key
    print(f"Cache: {compute.cache}")


# =============================================================================
# 7. REAL-WORLD EXAMPLES AND BEST PRACTICES
# =============================================================================

print("\n" + "=" * 60)
print("7. REAL-WORLD EXAMPLES AND BEST PRACTICES")
print("=" * 60)

def data_processing_pipeline():
    print("\n--- Data Processing Pipeline ---")
    
    # Sample data
    raw_data = [
        {'name': 'Alice', 'age': 25, 'score': 85, 'city': 'New York'},
        {'name': 'Bob', 'age': 30, 'score': 92, 'city': 'San Francisco'},
        {'name': 'Charlie', 'age': 22, 'score': 78, 'city': 'Chicago'},
        {'name': 'Diana', 'age': 28, 'score': 96, 'city': 'Boston'},
        {'name': 'Eve', 'age': 35, 'score': 88, 'city': 'Seattle'}
    ]
    
    # Processing pipeline using functional programming
    from functools import partial
    
    # Step 1: Filter adults (age >= 25)
    adults = filter(lambda person: person['age'] >= 25, raw_data)
    
    # Step 2: Add grade based on score
    def add_grade(person):
        score = person['score']
        if score >= 90:
            grade = 'A'
        elif score >= 80:
            grade = 'B'
        else:
            grade = 'C'
        return {**person, 'grade': grade}
    
    with_grades = map(add_grade, adults)
    
    # Step 3: Sort by score (descending)
    sorted_data = sorted(with_grades, key=lambda p: p['score'], reverse=True)
    
    # Step 4: Format output
    formatted = map(
        lambda p: f"{p['name']} ({p['age']}) - Grade {p['grade']} - {p['city']}", 
        sorted_data
    )
    
    print("Processed data:")
    for item in formatted:
        print(f"  {item}")
    
    # Alternative using generator pipeline
    def process_data_generator(data):
        # Filter adults
        adults = (person for person in data if person['age'] >= 25)
        
        # Add grades
        with_grades = (add_grade(person) for person in adults)
        
        # Sort (note: must materialize for sorting)
        sorted_data = sorted(with_grades, key=lambda p: p['score'], reverse=True)
        
        # Format
        for person in sorted_data:
            yield f"{person['name']} ({person['age']}) - Grade {person['grade']} - {person['city']}"
    
    print("\nUsing generator pipeline:")
    for item in process_data_generator(raw_data):
        print(f"  {item}")

def api_client_example():
    print("\n--- API Client with Advanced Features ---")
    
    class APIClient:
        def __init__(self, base_url, timeout=30):
            self.base_url = base_url
            self.timeout = timeout
            self.session_data = {}
        
        @lru_cache(maxsize=100)
        def get_cached(self, endpoint):
            """Cached GET request"""
            print(f"Making API call to {endpoint}")
            # Simulate API call
            time.sleep(0.1)
            return {'data': f'response from {endpoint}', 'timestamp': time.time()}
        
        @retry(max_attempts=3, delay=1)
        def reliable_request(self, endpoint):
            """Request with automatic retry"""
            import random
            if random.random() < 0.3:  # 30% failure rate
                raise Exception("Network error")
            return self.get_cached(endpoint)
        
        def batch_request(self, endpoints):
            """Batch multiple requests"""
            return list(map(self.reliable_request, endpoints))
        
        # Context manager for session management
        def __enter__(self):
            print("Starting API session")
            return self
        
        def __exit__(self, exc_type, exc_val, exc_tb):
            print("Closing API session")
            self.get_cached.cache_clear()
    
    # Usage
    with APIClient("https://api.example.com") as client:
        try:
            # Single request (with caching and retry)
            result1 = client.reliable_request("/users/1")
            result2 = client.reliable_request("/users/1")  # Cached
            
            # Batch requests
            endpoints = ["/users/2", "/users/3", "/posts/1"]
            batch_results = client.batch_request(endpoints)
            
            print("API calls completed successfully")
            print(f"Cache info: {client.get_cached.cache_info()}")
            
        except Exception as e:
            print(f"API error: {e}")

def performance_monitoring():
    print("\n--- Performance Monitoring Example ---")
    
    # Advanced timing decorator with statistics
    from collections import defaultdict
    import statistics
    
    class PerformanceMonitor:
        def __init__(self):
            self.call_times = defaultdict(list)
            self.call_counts = defaultdict(int)
        
        def monitor(self, func):
            @wraps(func)
            def wrapper(*args, **kwargs):
                start_time = time.time()
                try:
                    result = func(*args, **kwargs)
                    return result
                finally:
                    end_time = time.time()
                    duration = end_time - start_time
                    
                    func_name = func.__name__
                    self.call_times[func_name].append(duration)
                    self.call_counts[func_name] += 1
            return wrapper
        
        def get_stats(self, func_name):
            times = self.call_times[func_name]
            if not times:
                return None
            
            return {
                'count': len(times),
                'total_time': sum(times),
                'avg_time': statistics.mean(times),
                'min_time': min(times),
                'max_time': max(times),
                'median_time': statistics.median(times)
            }
        
        def report(self):
            print("\nPerformance Report:")
            print("-" * 50)
            for func_name in self.call_counts:
                stats = self.get_stats(func_name)
                print(f"{func_name}:")
                print(f"  Calls: {stats['count']}")
                print(f"  Total: {stats['total_time']:.4f}s")
                print(f"  Avg: {stats['avg_time']:.4f}s")
                print(f"  Min/Max: {stats['min_time']:.4f}s / {stats['max_time']:.4f}s")
    
    # Usage
    monitor = PerformanceMonitor()
    
    @monitor.monitor
    def database_query(query_id):
        # Simulate database query with variable time
        import random
        time.sleep(random.uniform(0.01, 0.1))
        return f"Result for query {query_id}"
    
    @monitor.monitor
    def data_processing(data_size):
        # Simulate data processing
        time.sleep(data_size * 0.01)
        return f"Processed {data_size} items"
    
    # Run some operations
    for i in range(5):
        database_query(i)
        data_processing(i * 10)
    
    monitor.report()


# =============================================================================
# MAIN EXECUTION AND BEST PRACTICES
# =============================================================================

if __name__ == "__main__":
    print("Python Advanced Concepts Tutorial")
    print("=" * 50)
    
    try:
        # Lambda expressions
        lambda_basics()
        lambda_advanced_patterns()
        lambda_gotchas()
        
        # Generators
        basic_generators()
        advanced_generators()
        generator_expressions_advanced()
        generator_methods()
        
        # Iterators
        iterator_examples()
        smart_range_demo()
        
        # Map, filter, functional programming
        map_advanced()
        filter_advanced()
        functional_programming_patterns()
        performance_comparison()
        
        # Dunder methods
        dunder_methods_demo()
        advanced_dunder_demo()
        special_dunder_patterns()
        
        # Functools
        functools_basics()
        functools_advanced()
        decorator_patterns()
        functional_composition()
        caching_strategies()
        
        # Real-world examples
        data_processing_pipeline()
        api_client_example()
        performance_monitoring()
        
    except KeyboardInterrupt:
        print("\nTutorial interrupted by user")
    except Exception as e:
        print(f"Tutorial error: {e}")
        import traceback
        traceback.print_exc()
    
    print("\n" + "=" * 60)
    print("TUTORIAL COMPLETE - BEST PRACTICES SUMMARY")
    print("=" * 60)
    print("""
KEY TAKEAWAYS:

Lambda Expressions:
- Use for simple, single-expression functions
- Great for key functions in sorting/filtering
- Watch out for closure gotchas with loops
- Consider readability - complex logic should use def

Generators:
- Excellent for memory efficiency with large datasets
- Use for data pipelines and streaming processing
- Remember they're lazy and single-use
- Use send(), throw(), close() for advanced control

Iterators:
- Implement __iter__ and __next__ for custom iteration
- Consider using generators instead of manual iterator classes
- Make iterators stateless when possible

Map/Filter/Functional Programming:
- Map/filter are lazy (return iterators)
- List comprehensions often more readable than map/filter
- Use itertools for advanced iteration patterns
- Compose functions for clean data pipelines

Dunder Methods:
- Make objects behave like built-in types
- Implement appropriate methods for your use case
- Use __slots__ for memory efficiency when needed
- Remember __hash__ and __eq__ relationship

Functools:
- Use @lru_cache for expensive computations
- @singledispatch for polymorphic functions
- partial() for function specialization
- @wraps for proper decorator metadata
- reduce() for fold operations

Performance Tips:
- Profile before optimizing
- Use generators for memory efficiency
- Cache expensive operations
- Consider algorithmic complexity
- Monitor and measure real usage patterns
    """)