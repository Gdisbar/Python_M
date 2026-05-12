"""
Python Collections Module - Complete Tutorial
============================================

Focus on commonly used collections with comprehensive examples,
plus brief coverage of specialized containers.

Most Used (Detailed Coverage):
- Counter
- defaultdict
- deque
- OrderedDict (though dict in Python 3.7+ maintains order)

Less Common (Overview):
- namedtuple
- ChainMap
- UserDict, UserList, UserString

"""

from collections import (
    Counter, defaultdict, deque, OrderedDict, namedtuple,
    ChainMap, UserDict, UserList, UserString
)
import json
import time
import random
from typing import Any, Dict, List


# =============================================================================
# 1. COUNTER - MOST COMMONLY USED
# =============================================================================

print("=" * 70)
print("1. COUNTER - COMPREHENSIVE GUIDE")
print("=" * 70)

def counter_basics():
    print("\n--- Counter Basics ---")
    
    # Creating Counters
    from collections import Counter
    
    # From iterables
    word = "hello world"
    char_count = Counter(word)
    print(f"Character count: {char_count}")
    
    # From lists
    numbers = [1, 2, 2, 3, 3, 3, 4, 4, 4, 4]
    num_count = Counter(numbers)
    print(f"Number count: {num_count}")
    
    # From dictionary
    dict_count = Counter({'a': 3, 'b': 1})
    print(f"From dict: {dict_count}")
    
    # From keyword arguments
    kw_count = Counter(cats=4, dogs=2)
    print(f"From kwargs: {kw_count}")
    
    # Empty counter
    empty = Counter()
    print(f"Empty counter: {empty}")

def counter_methods_comprehensive():
    print("\n--- Counter Methods - Deep Dive ---")
    
    # Sample data for examples
    text = """
    Python is amazing. Python is powerful. 
    Programming with Python is fun and Python developers are productive.
    """
    
    words = text.lower().split()
    word_counter = Counter(words)
    print(f"Word frequencies: {word_counter}")
    
    # 1. most_common() - THE MOST IMPORTANT METHOD
    print("\n1. most_common() usage:")
    print(f"Top 3 words: {word_counter.most_common(3)}")
    print(f"All words (sorted): {word_counter.most_common()}")
    
    # Least common (reverse)
    print(f"Least common: {word_counter.most_common()[:-4:-1]}")
    
    # 2. elements() - expand back to original
    print(f"\n2. elements() example:")
    small_counter = Counter({'a': 3, 'b': 2})
    print(f"Elements: {list(small_counter.elements())}")
    
    # 3. update() vs +=
    print(f"\n3. update() and arithmetic:")
    c1 = Counter(['a', 'b', 'c', 'a'])
    c2 = Counter(['a', 'b', 'b', 'd'])
    
    print(f"c1: {c1}")
    print(f"c2: {c2}")
    
    # update() modifies in place
    c1.update(c2)
    print(f"c1 after update: {c1}")
    
    # Reset for arithmetic demo
    c1 = Counter(['a', 'b', 'c', 'a'])
    
    # Arithmetic operations (return new Counter)
    print(f"c1 + c2: {c1 + c2}")  # Add counts
    print(f"c1 - c2: {c1 - c2}")  # Subtract (keep positive only)
    print(f"c1 & c2: {c1 & c2}")  # Intersection (min counts)
    print(f"c1 | c2: {c1 | c2}")  # Union (max counts)
    
    # 4. subtract() - different from -
    print(f"\n4. subtract() vs - operator:")
    c1 = Counter(['a', 'b', 'c', 'a'])
    c2 = Counter(['a', 'b', 'b'])
    
    print(f"Before subtract: {c1}")
    c1.subtract(c2)  # Can result in negative counts
    print(f"After subtract(): {c1}")
    
    # Compare with - operator
    c1 = Counter(['a', 'b', 'c', 'a'])
    result = c1 - c2  # Only keeps positive counts
    print(f"Using - operator: {result}")

def counter_real_world_examples():
    print("\n--- Counter Real-World Applications ---")
    
    # 1. Log Analysis
    print("1. Log Analysis Example:")
    log_entries = [
        "2023-01-01 10:00:00 INFO User login successful",
        "2023-01-01 10:01:00 ERROR Database connection failed",
        "2023-01-01 10:02:00 INFO User logout",
        "2023-01-01 10:03:00 ERROR Authentication failed",
        "2023-01-01 10:04:00 INFO User login successful",
        "2023-01-01 10:05:00 ERROR Database connection failed",
        "2023-01-01 10:06:00 WARNING Low disk space"
    ]
    
    # Extract log levels
    log_levels = [line.split()[2] for line in log_entries]
    level_count = Counter(log_levels)
    
    print("Log level distribution:")
    for level, count in level_count.most_common():
        print(f"  {level}: {count}")
    
    # 2. Text Analysis and NLP preprocessing
    print("\n2. Text Analysis:")
    
    def analyze_text(text):
        # Clean and tokenize
        import re
        words = re.findall(r'\b[a-zA-Z]+\b', text.lower())
        
        word_freq = Counter(words)
        
        # Statistics
        total_words = sum(word_freq.values())
        unique_words = len(word_freq)
        
        print(f"Total words: {total_words}")
        print(f"Unique words: {unique_words}")
        print(f"Vocabulary richness: {unique_words/total_words:.2%}")
        
        # Most common words (excluding stop words)
        stop_words = {'the', 'is', 'and', 'with', 'are', 'a', 'an', 'in', 'on', 'at'}
        content_words = Counter({word: count for word, count in word_freq.items() 
                               if word not in stop_words})
        
        print("Most common content words:")
        for word, count in content_words.most_common(5):
            print(f"  {word}: {count}")
        
        return word_freq
    
    sample_text = """
    Machine learning is transforming the world. Deep learning models
    are becoming more sophisticated. Natural language processing enables
    computers to understand human language. Python is the preferred
    language for machine learning projects.
    """
    
    analyze_text(sample_text)
    
    # 3. Data Validation and Quality Checking
    print("\n3. Data Quality Checking:")
    
    # Simulate dataset with quality issues
    user_data = [
        {'age': 25, 'country': 'USA', 'status': 'active'},
        {'age': None, 'country': 'Canada', 'status': 'active'},
        {'age': 30, 'country': 'USA', 'status': 'inactive'},
        {'age': 22, 'country': '', 'status': 'active'},
        {'age': 35, 'country': 'Mexico', 'status': 'active'},
        {'age': None, 'country': 'USA', 'status': 'pending'}
    ]
    
    def check_data_quality(data, field):
        values = [record.get(field) for record in data]
        
        # Count all values including None and empty strings
        all_values = Counter(str(v) if v is not None else 'NULL' for v in values)
        non_null_values = Counter(v for v in values if v is not None and v != '')
        
        print(f"\nField: {field}")
        print(f"All values: {dict(all_values)}")
        print(f"Non-null distribution: {dict(non_null_values)}")
        print(f"Null/Empty count: {all_values.get('NULL', 0) + all_values.get('', 0)}")
    
    for field in ['age', 'country', 'status']:
        check_data_quality(user_data, field)

def counter_advanced_patterns():
    print("\n--- Advanced Counter Patterns ---")
    
    # 1. Rolling Counter for streaming data
    class RollingCounter:
        def __init__(self, window_size=1000):
            self.window_size = window_size
            self.data = deque(maxlen=window_size)
            self._counter = Counter()
        
        def add(self, item):
            # Remove oldest item if at capacity
            if len(self.data) == self.window_size:
                oldest = self.data[0]
                self._counter[oldest] -= 1
                if self._counter[oldest] == 0:
                    del self._counter[oldest]
            
            # Add new item
            self.data.append(item)
            self._counter[item] += 1
        
        def get_counts(self):
            return dict(self._counter)
        
        def most_common(self, n=None):
            return self._counter.most_common(n)
    
    # Demo rolling counter
    print("1. Rolling Counter Demo:")
    rolling = RollingCounter(window_size=5)
    
    for item in ['a', 'b', 'a', 'c', 'b', 'a', 'd', 'c']:
        rolling.add(item)
        print(f"Added '{item}': {rolling.get_counts()}")
    
    # 2. Counter-based caching/memoization
    print("\n2. Counter for Cache Statistics:")
    
    class CachedFunction:
        def __init__(self, func):
            self.func = func
            self.cache = {}
            self.stats = Counter()
        
        def __call__(self, *args):
            if args in self.cache:
                self.stats['hits'] += 1
                return self.cache[args]
            
            self.stats['misses'] += 1
            result = self.func(*args)
            self.cache[args] = result
            return result
        
        def get_stats(self):
            total = sum(self.stats.values())
            if total == 0:
                return {"hit_rate": 0}
            return {
                "hit_rate": self.stats['hits'] / total,
                "total_calls": total,
                **dict(self.stats)
            }
    
    @CachedFunction
    def expensive_computation(n):
        time.sleep(0.01)  # Simulate expensive operation
        return n ** 2
    
    # Test cache
    for _ in range(10):
        expensive_computation(random.randint(1, 5))
    
    print(f"Cache stats: {expensive_computation.get_stats()}")
    
    # 3. Multi-dimensional counting
    print("\n3. Multi-dimensional Counter:")
    
    class MultiCounter:
        def __init__(self):
            self.counters = defaultdict(Counter)
        
        def add(self, category, item):
            self.counters[category][item] += 1
        
        def get_category_totals(self):
            return {cat: sum(counter.values()) for cat, counter in self.counters.items()}
        
        def get_top_items_per_category(self, n=3):
            return {cat: counter.most_common(n) for cat, counter in self.counters.items()}
    
    # Example: Website analytics
    analytics = MultiCounter()
    
    # Simulate page visits
    visits = [
        ('homepage', 'chrome'), ('homepage', 'firefox'),
        ('products', 'chrome'), ('products', 'safari'),
        ('about', 'chrome'), ('homepage', 'chrome'),
        ('contact', 'edge'), ('products', 'chrome')
    ]
    
    for page, browser in visits:
        analytics.add(page, browser)
    
    print("Category totals:", analytics.get_category_totals())
    print("Top browsers per page:", analytics.get_top_items_per_category(2))


# =============================================================================
# 2. DEFAULTDICT - SECOND MOST COMMONLY USED
# =============================================================================

print("\n" + "=" * 70)
print("2. DEFAULTDICT - COMPREHENSIVE GUIDE")
print("=" * 70)

def defaultdict_basics():
    print("\n--- Defaultdict Basics ---")
    
    # Basic usage - no more KeyError
    dd_list = defaultdict(list)
    dd_int = defaultdict(int)
    dd_set = defaultdict(set)
    
    # Demonstrate the difference
    regular_dict = {}
    
    try:
        regular_dict['missing_key'].append('value')
    except KeyError as e:
        print(f"Regular dict KeyError: {e}")
    
    # defaultdict handles missing keys gracefully
    dd_list['missing_key'].append('value')
    print(f"defaultdict result: {dict(dd_list)}")
    
    # Different default factories
    dd_int['counter'] += 1
    dd_int['counter'] += 5
    print(f"Int defaultdict: {dict(dd_int)}")
    
    dd_set['tags'].add('python')
    dd_set['tags'].add('tutorial')
    print(f"Set defaultdict: {dict(dd_set)}")

def defaultdict_real_world_examples():
    print("\n--- Defaultdict Real-World Applications ---")
    
    # 1. Grouping data (MOST COMMON USE CASE)
    print("1. Data Grouping:")
    
    # Group students by grade
    students = [
        {'name': 'Alice', 'grade': 'A', 'subject': 'Math'},
        {'name': 'Bob', 'grade': 'B', 'subject': 'Science'},
        {'name': 'Charlie', 'grade': 'A', 'subject': 'Math'},
        {'name': 'Diana', 'grade': 'A', 'subject': 'Science'},
        {'name': 'Eve', 'grade': 'B', 'subject': 'Math'}
    ]
    
    # Group by grade
    by_grade = defaultdict(list)
    for student in students:
        by_grade[student['grade']].append(student['name'])
    
    print("Students by grade:")
    for grade, names in by_grade.items():
        print(f"  Grade {grade}: {names}")
    
    # Group by multiple criteria
    by_grade_subject = defaultdict(lambda: defaultdict(list))
    for student in students:
        by_grade_subject[student['grade']][student['subject']].append(student['name'])
    
    print("\nStudents by grade and subject:")
    for grade, subjects in by_grade_subject.items():
        print(f"Grade {grade}:")
        for subject, names in subjects.items():
            print(f"  {subject}: {names}")
    
    # 2. Building graphs/networks
    print("\n2. Graph Representation:")
    
    # Adjacency list using defaultdict
    graph = defaultdict(list)
    
    edges = [
        ('A', 'B'), ('A', 'C'), ('B', 'D'), 
        ('C', 'D'), ('D', 'E'), ('B', 'E')
    ]
    
    # Build undirected graph
    for u, v in edges:
        graph[u].append(v)
        graph[v].append(u)
    
    print("Graph adjacency list:")
    for node, neighbors in graph.items():
        print(f"  {node}: {neighbors}")
    
    def find_path(graph, start, end, path=None):
        """Simple path finding using the graph"""
        if path is None:
            path = []
        
        path = path + [start]
        
        if start == end:
            return path
        
        for node in graph[start]:
            if node not in path:
                new_path = find_path(graph, node, end, path)
                if new_path:
                    return new_path
        
        return None
    
    path = find_path(graph, 'A', 'E')
    print(f"Path from A to E: {path}")
    
    # 3. Nested data structures
    print("\n3. Nested Structures:")
    
    # Nested defaultdict for hierarchical data
    def nested_dict():
        return defaultdict(nested_dict)
    
    # Company -> Department -> Employee -> Info
    company = nested_dict()
    
    company['Engineering']['Backend']['Alice'] = {'salary': 120000, 'level': 'Senior'}
    company['Engineering']['Frontend']['Bob'] = {'salary': 100000, 'level': 'Mid'}
    company['Sales']['Regional']['Charlie'] = {'salary': 80000, 'level': 'Junior'}
    
    print("Company structure:")
    print(json.dumps(company, indent=2, default=dict))
    
    # 4. Counting with categories
    print("\n4. Categorical Counting:")
    
    # Website analytics
    analytics = defaultdict(lambda: defaultdict(int))
    
    # Log entries: (timestamp, page, user_type, action)
    logs = [
        ('2023-01-01', 'homepage', 'guest', 'view'),
        ('2023-01-01', 'homepage', 'user', 'view'),
        ('2023-01-01', 'products', 'user', 'view'),
        ('2023-01-01', 'products', 'user', 'purchase'),
        ('2023-01-02', 'homepage', 'guest', 'view'),
        ('2023-01-02', 'about', 'user', 'view'),
    ]
    
    for date, page, user_type, action in logs:
        analytics[page][user_type] += 1
    
    print("Page analytics:")
    for page, user_data in analytics.items():
        print(f"{page}: {dict(user_data)}")

def defaultdict_advanced_patterns():
    print("\n--- Advanced Defaultdict Patterns ---")
    
    # 1. Custom factory functions
    print("1. Custom Factory Functions:")
    
    def random_color():
        colors = ['red', 'blue', 'green', 'yellow', 'purple']
        return random.choice(colors)
    
    def timestamp_factory():
        return time.time()
    
    # User preferences with defaults
    user_prefs = defaultdict(lambda: {
        'theme': 'light',
        'notifications': True,
        'language': 'en'
    })
    
    # Time-based data
    timestamps = defaultdict(timestamp_factory)
    
    print(f"New user prefs: {user_prefs['new_user']}")
    print(f"Access timestamp: {timestamps['page_visit']}")
    
    # 2. defaultdict with Counter
    print("\n2. Combining defaultdict with Counter:")
    
    # Word frequency by document
    documents = [
        "python is great for data science",
        "java is popular for enterprise applications", 
        "python has simple syntax and great libraries",
        "javascript runs in browsers and servers"
    ]
    
    word_freq_by_doc = defaultdict(Counter)
    
    for i, doc in enumerate(documents):
        words = doc.lower().split()
        word_freq_by_doc[f'doc_{i}'].update(words)
    
    print("Word frequencies by document:")
    for doc_id, counter in word_freq_by_doc.items():
        print(f"{doc_id}: {dict(counter.most_common(3))}")
    
    # 3. Memoization with defaultdict
    print("\n3. Memoization Pattern:")
    
    # Fibonacci with defaultdict memoization
    fib_cache = defaultdict(int)
    fib_cache[0] = 0
    fib_cache[1] = 1
    
    def fibonacci(n):
        if n not in fib_cache:
            fib_cache[n] = fibonacci(n-1) + fibonacci(n-2)
        return fib_cache[n]
    
    print(f"Fibonacci(20): {fibonacci(20)}")
    print(f"Cache size: {len(fib_cache)}")
    
    # 4. State machines with defaultdict
    print("\n4. State Machine Pattern:")
    
    class SimpleStateMachine:
        def __init__(self):
            self.transitions = defaultdict(dict)
            self.current_state = 'initial'
        
        def add_transition(self, from_state, event, to_state):
            self.transitions[from_state][event] = to_state
        
        def trigger(self, event):
            if event in self.transitions[self.current_state]:
                old_state = self.current_state
                self.current_state = self.transitions[self.current_state][event]
                print(f"State: {old_state} --({event})--> {self.current_state}")
                return True
            else:
                print(f"No transition for event '{event}' from state '{self.current_state}'")
                return False
    
    # Door state machine
    door = SimpleStateMachine()
    door.add_transition('closed', 'open', 'open')
    door.add_transition('open', 'close', 'closed')
    door.add_transition('closed', 'lock', 'locked')
    door.add_transition('locked', 'unlock', 'closed')
    
    door.current_state = 'closed'
    door.trigger('open')
    door.trigger('close')
    door.trigger('lock')
    door.trigger('open')  # Should fail
    door.trigger('unlock')


# =============================================================================
# 3. DEQUE - THIRD MOST COMMONLY USED
# =============================================================================

print("\n" + "=" * 70)
print("3. DEQUE - COMPREHENSIVE GUIDE")
print("=" * 70)

def deque_basics():
    print("\n--- Deque Basics ---")
    
    # Creating deques
    d = deque([1, 2, 3, 4, 5])
    print(f"Basic deque: {d}")
    
    # Key operations - O(1) at both ends
    d.append(6)        # Add to right
    d.appendleft(0)    # Add to left
    print(f"After appends: {d}")
    
    d.pop()           # Remove from right
    d.popleft()       # Remove from left
    print(f"After pops: {d}")
    
    # Rotation (very useful!)
    d.rotate(2)       # Rotate right by 2
    print(f"After rotate(2): {d}")
    
    d.rotate(-1)      # Rotate left by 1
    print(f"After rotate(-1): {d}")
    
    # maxlen - creates a bounded deque
    bounded = deque([1, 2, 3], maxlen=3)
    print(f"Bounded deque: {bounded}")
    
    bounded.append(4)  # Automatically removes from left
    print(f"After append to bounded: {bounded}")

def deque_vs_list_performance():
    print("\n--- Performance Comparison ---")
    
    import timeit
    
    # Setup code
    setup_code = """
from collections import deque
import random

# Large datasets
large_list = list(range(100000))
large_deque = deque(range(100000))
"""
    
    # Test append operations
    list_append_time = timeit.timeit(
        'large_list.append(1)',
        setup=setup_code,
        number=10000
    )
    
    deque_append_time = timeit.timeit(
        'large_deque.append(1)',
        setup=setup_code,
        number=10000
    )
    
    # Test left operations
    list_insert_time = timeit.timeit(
        'large_list.insert(0, 1)',
        setup=setup_code,
        number=1000  # Fewer iterations because list.insert(0) is slow
    )
    
    deque_appendleft_time = timeit.timeit(
        'large_deque.appendleft(1)',
        setup=setup_code,
        number=10000
    )
    
    print(f"Append performance:")
    print(f"  List:  {list_append_time:.6f}s")
    print(f"  Deque: {deque_append_time:.6f}s")
    print(f"  Ratio: {list_append_time/deque_append_time:.2f}x")
    
    print(f"\nLeft insertion performance:")
    print(f"  List insert(0):   {list_insert_time:.6f}s")
    print(f"  Deque appendleft: {deque_appendleft_time:.6f}s")
    print(f"  Ratio: {list_insert_time/deque_appendleft_time:.2f}x")

def deque_real_world_applications():
    print("\n--- Deque Real-World Applications ---")
    
    # 1. Sliding window operations (VERY COMMON)
    print("1. Sliding Window Maximum:")
    
    def sliding_window_maximum(arr, k):
        """Find maximum in each sliding window of size k"""
        if not arr or k == 0:
            return []
        
        # Use deque to store indices
        dq = deque()
        result = []
        
        for i in range(len(arr)):
            # Remove indices outside current window
            while dq and dq[0] <= i - k:
                dq.popleft()
            
            # Remove indices with smaller values (not useful)
            while dq and arr[dq[-1]] <= arr[i]:
                dq.pop()
            
            dq.append(i)
            
            # Add to result when window is full
            if i >= k - 1:
                result.append(arr[dq[0]])
        
        return result
    
    arr = [1, 3, -1, -3, 5, 3, 6, 7]
    k = 3
    result = sliding_window_maximum(arr, k)
    print(f"Array: {arr}")
    print(f"Sliding window max (k={k}): {result}")
    
    # 2. Undo/Redo functionality
    print("\n2. Undo/Redo System:")
    
    class UndoRedoSystem:
        def __init__(self, max_history=10):
            self.history = deque(maxlen=max_history)
            self.redo_stack = deque()
            self.current_state = None
        
        def execute_command(self, command, state):
            # Save current state for undo
            if self.current_state is not None:
                self.history.append(self.current_state)
            
            # Clear redo stack on new command
            self.redo_stack.clear()
            
            # Execute command
            self.current_state = state
            print(f"Executed: {command} -> State: {state}")
        
        def undo(self):
            if not self.history:
                print("Nothing to undo")
                return
            
            # Save current state for redo
            self.redo_stack.append(self.current_state)
            
            # Restore previous state
            self.current_state = self.history.pop()
            print(f"Undo -> State: {self.current_state}")
        
        def redo(self):
            if not self.redo_stack:
                print("Nothing to redo")
                return
            
            # Save current state for undo
            self.history.append(self.current_state)
            
            # Restore next state
            self.current_state = self.redo_stack.pop()
            print(f"Redo -> State: {self.current_state}")
    
    # Demo undo/redo
    editor = UndoRedoSystem()
    editor.execute_command("type 'Hello'", "Hello")
    editor.execute_command("type ' World'", "Hello World")
    editor.execute_command("delete 5 chars", "Hello")
    
    editor.undo()  # Back to "Hello World"
    editor.undo()  # Back to "Hello"
    editor.redo()  # Forward to "Hello World"
    
    # 3. Recent items cache
    print("\n3. Recent Items Cache:")
    
    class RecentItemsCache:
        def __init__(self, max_size=5):
            self.items = deque(maxlen=max_size)
            self.item_set = set()  # For O(1) lookups
        
        def add(self, item):
            # If item already exists, remove it first
            if item in self.item_set:
                self.items.remove(item)
                self.item_set.remove(item)
            
            # Add to front
            self.items.appendleft(item)
            self.item_set.add(item)
            
            # Handle maxlen overflow
            if len(self.item_set) > len(self.items):
                # An item was auto-removed by deque
                self.item_set = set(self.items)
        
        def get_recent(self):
            return list(self.items)
    
    cache = RecentItemsCache(max_size=3)
    
    for item in ['file1.txt', 'file2.txt', 'file3.txt', 'file1.txt', 'file4.txt']:
        cache.add(item)
        print(f"Added '{item}': Recent = {cache.get_recent()}")
    
    # 4. Round-robin scheduler
    print("\n4. Round-Robin Task Scheduler:")
    
    class RoundRobinScheduler:
        def __init__(self):
            self.tasks = deque()
        
        def add_task(self, task_name):
            self.tasks.append(task_name)
            print(f"Added task: {task_name}")
        
        def execute_next(self):
            if not self.tasks:
                print("No tasks to execute")
                return None
            
            # Get next task and rotate to end
            task = self.tasks[0]
            self.tasks.rotate(-1)
            print(f"Executing: {task}")
            return task
        
        def remove_task(self, task_name):
            try:
                self.tasks.remove(task_name)
                print(f"Removed task: {task_name}")
            except ValueError:
                print(f"Task not found: {task_name}")
        
        def show_queue(self):
            print(f"Task queue: {list(self.tasks)}")
    
    scheduler = RoundRobinScheduler()
    
    for task in ['Email', 'Backup', 'Monitoring', 'Cleanup']:
        scheduler.add_task(task)
    
    scheduler.show_queue()
    
    # Execute some tasks
    for _ in range(6):
        scheduler.execute_next()
    
    scheduler.show_queue()

def deque_advanced_patterns():
    print("\n--- Advanced Deque Patterns ---")
    
    # 1. Palindrome checker using deque
    print("1. Palindrome Checker:")
    
    def is_palindrome(text):
        # Clean text: only alphanumeric, lowercase
        clean = ''.join(c.lower() for c in text if c.isalnum())
        chars = deque(clean)
        
        while len(chars) > 1:
            if chars.popleft() != chars.pop():
                return False
        return True
    
    test_strings = [
        "A man a plan a canal Panama",
        "race a car",
        "hello world",
        "Madam"
    ]
    
    for text in test_strings:
        result = is_palindrome(text)
        print(f"'{text}': {result}")
    
    # 2. Moving average with deque
    print("\n2. Moving Average Calculator:")
    
    class MovingAverage:
        def __init__(self, window_size):
            self.window_size = window_size
            self.window = deque(maxlen=window_size)
            self.sum = 0
        
        def add_value(self, value):
            # If window is full, subtract the value that will be removed
            if len(self.window) == self.window_size:
                self.sum -= self.window[0]
            
            # Add new value
            self.window.append(value)
            self.sum += value
            
            return self.sum / len(self.window)
        
        def get_current_average(self):
            return self.sum / len(self.window) if self.window else 0
    
    ma = MovingAverage(3)
    values = [10, 20, 30, 40, 50, 60]
    
    for value in values:
        avg = ma.add_value(value)
        print(f"Added {value}: Moving avg = {avg:.2f}")
    
    # 3. BFS traversal using deque
    print("\n3. Breadth-First Search:")
    
    def bfs_shortest_path(graph, start, end):
        if start == end:
            return [start]
        
        queue = deque([(start, [start])])
        visited = {start}
        
        while queue:
            node, path = queue.popleft()
            
            for neighbor in graph.get(node, []):
                if neighbor == end:
                    return path + [neighbor]
                
                if neighbor not in visited:
                    visited.add(neighbor)
                    queue.append((neighbor, path + [neighbor]))
        
        return None  # No path found
    
    # Example graph
    graph = {
        'A': ['B', 'C'],
        'B': ['A', 'D', 'E'],
        'C': ['A', 'F'],
        'D': ['B'],
        'E': ['B', 'F'],
        'F': ['C', 'E']
    }
    
    path = bfs_shortest_path(graph, 'A', 'F')
    print(f"Shortest path from A to F: {path}")
    
    # 4. Rate limiting with token bucket
    print("\n4. Rate Limiter (Token Bucket):")
    
    class TokenBucket:
        def __init__(self, capacity, refill_rate):
            self.capacity = capacity
            self.tokens = deque(maxlen=capacity)
            self.refill_rate = refill_rate  # tokens per second
            self.last_refill = time.time()
        
        def _refill(self):
            now = time.time()
            elapsed = now - self.last_refill
            tokens_to_add = int(elapsed * self.refill_rate)
            
            for _ in range(min(tokens_to_add, self.capacity - len(self.tokens))):
                self.tokens.append(now)
            
            self.last_refill = now
        
        def consume(self, tokens_needed=1):
            self._refill()
            
            if len(self.tokens) >= tokens_needed:
                for _ in range(tokens_needed):
                    self.tokens.popleft()
                return True
            return False
        
        def available_tokens(self):
            self._refill()
            return len(self.tokens)
    
    # Example: 5 requests per second, burst capacity of 10
    limiter = TokenBucket(capacity=10, refill_rate=5)
    
    print("Rate limiter demo (5 tokens/sec, capacity 10):")
    for i in range(12):
        allowed = limiter.consume()
        tokens_left = limiter.available_tokens()
        print(f"Request {i+1}: {'✓' if allowed else '✗'} (tokens left: {tokens_left})")
        time.sleep(0.1)


# =============================================================================
# 4. ORDEREDDICT - LESS IMPORTANT SINCE PYTHON 3.7+
# =============================================================================

print("\n" + "=" * 70)
print("4. ORDEREDDICT - OVERVIEW (Less Important Since Python 3.7+)")
print("=" * 70)

def ordereddict_overview():
    print("\n--- OrderedDict Overview ---")
    
    # Note: Regular dicts maintain insertion order since Python 3.7
    print("NOTE: Regular dict maintains order since Python 3.7+")
    
    regular_dict = {'a': 1, 'b': 2, 'c': 3}
    ordered_dict = OrderedDict([('a', 1), ('b', 2), ('c', 3)])
    
    print(f"Regular dict: {regular_dict}")
    print(f"OrderedDict:  {ordered_dict}")
    
    # Key differences that still matter
    print("\nStill useful for:")
    
    # 1. move_to_end() method
    ordered_dict.move_to_end('a')  # Move 'a' to end
    print(f"After move_to_end('a'): {ordered_dict}")
    
    ordered_dict.move_to_end('c', last=False)  # Move 'c' to beginning
    print(f"After move_to_end('c', last=False): {ordered_dict}")
    
    # 2. Equality comparison considers order
    dict1 = {'a': 1, 'b': 2}
    dict2 = {'b': 2, 'a': 1}
    
    odict1 = OrderedDict([('a', 1), ('b', 2)])
    odict2 = OrderedDict([('b', 2), ('a', 1)])
    
    print(f"\nRegular dict equality (ignores order): {dict1 == dict2}")
    print(f"OrderedDict equality (considers order): {odict1 == odict2}")
    
    # 3. LRU Cache implementation
    print("\n--- LRU Cache with OrderedDict ---")
    
    class LRUCache:
        def __init__(self, capacity):
            self.capacity = capacity
            self.cache = OrderedDict()
        
        def get(self, key):
            if key not in self.cache:
                return None
            
            # Move to end (most recently used)
            self.cache.move_to_end(key)
            return self.cache[key]
        
        def put(self, key, value):
            if key in self.cache:
                # Update and move to end
                self.cache[key] = value
                self.cache.move_to_end(key)
            else:
                # Add new item
                if len(self.cache) >= self.capacity:
                    # Remove least recently used (first item)
                    self.cache.popitem(last=False)
                
                self.cache[key] = value
        
        def __repr__(self):
            return f"LRUCache({dict(self.cache)})"
    
    lru = LRUCache(3)
    
    # Test LRU cache
    lru.put('a', 1)
    lru.put('b', 2)
    lru.put('c', 3)
    print(f"After adding a,b,c: {lru}")
    
    lru.get('a')  # Access 'a' - moves to end
    print(f"After accessing 'a': {lru}")
    
    lru.put('d', 4)  # Should evict 'b' (least recently used)
    print(f"After adding 'd': {lru}")


# =============================================================================
# 5. NAMEDTUPLE - BRIEF COVERAGE
# =============================================================================

print("\n" + "=" * 70)
print("5. NAMEDTUPLE - BRIEF OVERVIEW")
print("=" * 70)

def namedtuple_overview():
    print("\n--- Namedtuple Quick Guide ---")
    
    # Creating namedtuple
    Point = namedtuple('Point', ['x', 'y'])
    Person = namedtuple('Person', 'name age city')  # Space-separated also works
    
    # Usage
    p1 = Point(1, 2)
    person1 = Person('Alice', 30, 'New York')
    
    print(f"Point: {p1}")
    print(f"Person: {person1}")
    
    # Access by name or index
    print(f"Point x: {p1.x}, Point[0]: {p1[0]}")
    print(f"Person name: {person1.name}")
    
    # Immutable (like tuple)
    try:
        p1.x = 5  # This will fail
    except AttributeError as e:
        print(f"Immutable: {e}")
    
    # Useful methods
    print(f"As dict: {person1._asdict()}")
    print(f"Fields: {person1._fields}")
    
    # _replace() for "updating"
    person2 = person1._replace(age=31)
    print(f"Updated person: {person2}")
    
    # When to use namedtuple:
    print("\nUse namedtuple when you need:")
    print("- Lightweight, immutable data structures")
    print("- Better readability than plain tuples") 
    print("- Memory efficiency (less than classes)")
    print("- But consider dataclasses for more features")


# =============================================================================
# 6. LESS COMMON COLLECTIONS - BRIEF OVERVIEW
# =============================================================================

print("\n" + "=" * 70)
print("6. LESS COMMON COLLECTIONS - BRIEF OVERVIEW")
print("=" * 70)

def chainmap_overview():
    print("\n--- ChainMap - Quick Look ---")
    
    # ChainMap groups multiple dicts into a single view
    defaults = {'color': 'blue', 'size': 'medium'}
    user_prefs = {'color': 'red'}
    
    combined = ChainMap(user_prefs, defaults)
    print(f"ChainMap: {dict(combined)}")
    print(f"Color (user overrides default): {combined['color']}")
    print(f"Size (from defaults): {combined['size']}")
    
    # Use case: Configuration with fallbacks
    print("\nUse case: Configuration hierarchy")
    
    # Command line args -> environment -> config file -> defaults
    cmd_args = {'debug': True}
    env_vars = {'host': 'localhost'}
    config_file = {'port': 8080, 'host': 'production.com'}
    defaults = {'host': '127.0.0.1', 'port': 80, 'debug': False}
    
    config = ChainMap(cmd_args, env_vars, config_file, defaults)
    
    print("Configuration priority chain:")
    for key in ['debug', 'host', 'port']:
        print(f"  {key}: {config[key]}")

def userdict_overview():
    print("\n--- UserDict, UserList, UserString - Quick Look ---")
    
    print("These are rarely used base classes for creating dict/list/str-like objects")
    print("Mostly replaced by inheriting from built-in types directly")
    
    # Quick example of UserDict
    class CaseInsensitiveDict(UserDict):
        def __setitem__(self, key, value):
            super().__setitem__(key.lower(), value)
        
        def __getitem__(self, key):
            return super().__getitem__(key.lower())
        
        def __contains__(self, key):
            return super().__contains__(key.lower())
    
    ci_dict = CaseInsensitiveDict()
    ci_dict['NAME'] = 'Alice'
    ci_dict['Age'] = 30
    
    print(f"Case-insensitive dict: {dict(ci_dict)}")
    print(f"ci_dict['name']: {ci_dict['name']}")  # Works with lowercase
    print(f"'NAME' in ci_dict: {'NAME' in ci_dict}")  # Case-insensitive check


# =============================================================================
# 7. PERFORMANCE COMPARISONS AND BEST PRACTICES
# =============================================================================

print("\n" + "=" * 70)
print("7. PERFORMANCE & BEST PRACTICES")
print("=" * 70)

def performance_comparisons():
    print("\n--- Performance Comparisons ---")
    
    import timeit
    
    # Counter vs manual counting
    data = ['apple', 'banana', 'apple', 'cherry', 'banana', 'apple'] * 1000
    
    def manual_count(items):
        counts = {}
        for item in items:
            counts[item] = counts.get(item, 0) + 1
        return counts
    
    def manual_count_defaultdict(items):
        counts = defaultdict(int)
        for item in items:
            counts[item] += 1
        return dict(counts)
    
    counter_time = timeit.timeit(
        lambda: Counter(data),
        number=1000
    )
    
    manual_time = timeit.timeit(
        lambda: manual_count(data),
        number=1000
    )
    
    defaultdict_time = timeit.timeit(
        lambda: manual_count_defaultdict(data),
        number=1000
    )
    
    print("Counting performance (1000 iterations):")
    print(f"  Counter:     {counter_time:.4f}s")
    print(f"  Manual dict: {manual_time:.4f}s")
    print(f"  defaultdict: {defaultdict_time:.4f}s")
    
    # Memory usage comparison
    import sys
    
    regular_dict = {i: i for i in range(1000)}
    default_dict = defaultdict(int, regular_dict)
    counter_obj = Counter(regular_dict)
    
    print(f"\nMemory usage for 1000 items:")
    print(f"  dict:        {sys.getsizeof(regular_dict)} bytes")
    print(f"  defaultdict: {sys.getsizeof(default_dict)} bytes")
    print(f"  Counter:     {sys.getsizeof(counter_obj)} bytes")

def best_practices():
    print("\n--- Best Practices Summary ---")
    
    practices = {
        "Counter": [
            "Use for frequency counting and statistical analysis",
            "Prefer Counter over manual dict counting",
            "Use most_common() for top-K problems",
            "Remember arithmetic operations (+, -, &, |)",
            "Use elements() to expand back to original data"
        ],
        "defaultdict": [
            "Use when you need default values for missing keys",
            "Perfect for grouping operations",
            "Great for nested data structures",
            "Use lambda for complex default factories",
            "Remember it's still a dict - use dict() to convert if needed"
        ],
        "deque": [
            "Use for O(1) operations at both ends",
            "Perfect for queues, stacks, and sliding windows",
            "Use maxlen for bounded collections",
            "Use rotate() for circular operations",
            "Prefer over list for frequent left-side operations"
        ],
        "OrderedDict": [
            "Less important since Python 3.7+ (dict maintains order)",
            "Still useful for move_to_end() functionality",
            "Use for LRU cache implementations",
            "Consider when order-aware equality is needed"
        ]
    }
    
    for collection, tips in practices.items():
        print(f"\n{collection}:")
        for tip in tips:
            print(f"  • {tip}")

def common_patterns_summary():
    print("\n--- Common Patterns Summary ---")
    
    patterns = {
        "Data Grouping": "defaultdict(list) + append",
        "Frequency Counting": "Counter(items)",
        "Top-K Items": "Counter(items).most_common(k)",
        "Sliding Window": "deque with maxlen",
        "BFS/Queue": "deque with append/popleft",
        "Undo/Redo": "deque for history stack",
        "LRU Cache": "OrderedDict with move_to_end",
        "Multi-level Dicts": "defaultdict(lambda: defaultdict(type))",
        "Rolling Statistics": "deque with maxlen + custom logic",
        "Rate Limiting": "deque with time-based expiration"
    }
    
    print("Most common usage patterns:")
    for pattern, implementation in patterns.items():
        print(f"  {pattern:15} → {implementation}")

def when_to_use_what():
    print("\n--- When to Use What? ---")
    
    scenarios = [
        ("Counting items/frequencies", "Counter"),
        ("Grouping data by key", "defaultdict(list)"),
        ("Need queue (FIFO)", "deque"),
        ("Need stack (LIFO)", "deque or list"),
        ("Sliding window operations", "deque with maxlen"),
        ("Missing key defaults", "defaultdict"),
        ("Nested dictionaries", "defaultdict(dict) or defaultdict(lambda: defaultdict(type))"),
        ("BFS graph traversal", "deque"),
        ("Undo/redo functionality", "deque"),
        ("LRU cache", "OrderedDict + move_to_end"),
        ("Configuration hierarchy", "ChainMap"),
        ("Lightweight data classes", "namedtuple or dataclasses")
    ]
    
    print("Scenario → Best Collection:")
    for scenario, collection in scenarios:
        print(f"  {scenario:25} → {collection}")


# =============================================================================
# MAIN EXECUTION
# =============================================================================

if __name__ == "__main__":
    print("Python Collections Module - Complete Tutorial")
    print("=" * 50)
    
    try:
        # DETAILED COVERAGE - Most Used
        print("\n🔥 MOST COMMONLY USED COLLECTIONS (Detailed)")
        print("=" * 50)
        
        # Counter - Most important
        counter_basics()
        counter_methods_comprehensive() 
        counter_real_world_examples()
        counter_advanced_patterns()
        
        # defaultdict - Second most important
        defaultdict_basics()
        defaultdict_real_world_examples()
        defaultdict_advanced_patterns()
        
        # deque - Third most important
        deque_basics()
        deque_vs_list_performance()
        deque_real_world_applications()
        deque_advanced_patterns()
        
        print("\n📚 MODERATELY USED COLLECTIONS (Overview)")
        print("=" * 50)
        
        # OrderedDict - Less important since Python 3.7+
        ordereddict_overview()
        
        print("\n⚡ RARELY USED COLLECTIONS (Brief)")
        print("=" * 50)
        
        # Brief coverage of less common ones
        namedtuple_overview()
        chainmap_overview()
        userdict_overview()
        
        print("\n🎯 PERFORMANCE & BEST PRACTICES")
        print("=" * 50)
        
        performance_comparisons()
        best_practices()
        common_patterns_summary()
        when_to_use_what()
        
    except KeyboardInterrupt:
        print("\nTutorial interrupted by user")
    except Exception as e:
        print(f"Tutorial error: {e}")
        import traceback
        traceback.print_exc()
    
    print("\n" + "=" * 70)
    print("COLLECTIONS TUTORIAL COMPLETE")
    print("=" * 70)
    print("""
🏆 KEY TAKEAWAYS:

MOST IMPORTANT (Use These Regularly):
┌─────────────────────────────────────────────────────────────┐
│ Counter    → Counting, frequency analysis, top-K problems  │
│ defaultdict→ Missing key handling, data grouping           │  
│ deque      → Queues, stacks, sliding windows, O(1) ends    │
└─────────────────────────────────────────────────────────────┘

MODERATELY IMPORTANT:
┌─────────────────────────────────────────────────────────────┐
│ OrderedDict→ LRU cache, order-sensitive operations         │
│ namedtuple → Lightweight immutable data structures         │
└─────────────────────────────────────────────────────────────┘

RARELY USED:
┌─────────────────────────────────────────────────────────────┐
│ ChainMap   → Configuration hierarchies                     │
│ UserDict   → Custom dict-like classes (use dict instead)   │
└─────────────────────────────────────────────────────────────┘

💡 PERFORMANCE TIPS:
• Counter: Fastest for counting operations
• defaultdict: Faster than dict.get() for missing keys
• deque: Much faster than list for left operations
• Regular dict: Maintains order since Python 3.7+

🎯 MOST COMMON PATTERNS:
• Data grouping: defaultdict(list)
• Frequency counting: Counter(items)
• Queue operations: deque()
• Sliding windows: deque(maxlen=n)
• Top-K items: Counter.most_common(k)
    """)