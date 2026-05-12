"""
Python Threading
==================================
"""

import threading
import time
import queue
import concurrent.futures
from threading import Lock, RLock, Semaphore, Event, Condition, Barrier
import random
import requests
import json


# =============================================================================
# 1. THREADING BASICS AND GIL UNDERSTANDING
# =============================================================================

print("=" * 60)
print("1. THREADING BASICS AND GIL")
print("=" * 60)

def cpu_bound_task(name, iterations=1000000):
    """CPU-intensive task - limited by GIL"""
    count = 0
    for i in range(iterations):
        count += i * i
    print(f"CPU task {name} completed: {count}")
    return count

def io_bound_task(name, delay=1):
    """I/O-intensive task - benefits from threading"""
    print(f"IO task {name} starting...")
    time.sleep(delay)  # Simulates I/O operation
    print(f"IO task {name} completed")
    return f"Result from {name}"

# Basic thread creation and execution
def basic_threading_example():
    print("\n--- Basic Threading ---")
    
    # Method 1: Using Thread class directly
    thread1 = threading.Thread(target=io_bound_task, args=("Thread-1", 2))
    thread2 = threading.Thread(target=io_bound_task, args=("Thread-2", 1))
    
    start_time = time.time()
    
    thread1.start()
    thread2.start()
    
    # Wait for threads to complete
    thread1.join()
    thread2.join()
    
    print(f"Total time: {time.time() - start_time:.2f}s")

# Method 2: Subclassing Thread
class CustomThread(threading.Thread):
    def __init__(self, name, delay):
        super().__init__()
        self.name = name
        self.delay = delay
        self.result = None
    
    def run(self):
        print(f"Custom thread {self.name} starting...")
        time.sleep(self.delay)
        self.result = f"Processed by {self.name}"
        print(f"Custom thread {self.name} finished")

def custom_thread_example():
    print("\n--- Custom Thread Class ---")
    
    threads = []
    for i in range(3):
        t = CustomThread(f"CustomThread-{i}", random.uniform(0.5, 2))
        threads.append(t)
        t.start()
    
    # Collect results
    for t in threads:
        t.join()
        print(f"Result: {t.result}")


# =============================================================================
# 2. THREAD SYNCHRONIZATION PRIMITIVES
# =============================================================================

print("\n" + "=" * 60)
print("2. THREAD SYNCHRONIZATION")
print("=" * 60)

# Shared resource without synchronization (problematic)
shared_counter = 0

def unsafe_increment():
    global shared_counter
    for _ in range(100000):
        shared_counter += 1

def race_condition_demo():
    print("\n--- Race Condition Demo ---")
    global shared_counter
    shared_counter = 0
    
    threads = []
    for i in range(5):
        t = threading.Thread(target=unsafe_increment)
        threads.append(t)
        t.start()
    
    for t in threads:
        t.join()
    
    print(f"Expected: 500000, Actual: {shared_counter}")
    print("Notice the inconsistent results due to race conditions")

# Lock for thread safety
safe_counter = 0
counter_lock = Lock()

def safe_increment():
    global safe_counter
    for _ in range(100000):
        with counter_lock:  # Context manager ensures lock release
            safe_counter += 1

def lock_demo():
    print("\n--- Lock Demo ---")
    global safe_counter
    safe_counter = 0
    
    threads = []
    for i in range(5):
        t = threading.Thread(target=safe_increment)
        threads.append(t)
        t.start()
    
    for t in threads:
        t.join()
    
    print(f"Expected: 500000, Actual: {safe_counter}")
    print("Consistent results with proper locking")

# RLock (Reentrant Lock) example
class ThreadSafeCounter:
    def __init__(self):
        self._value = 0
        self._lock = RLock()  # Allows same thread to acquire multiple times
    
    def increment(self):
        with self._lock:
            self._value += 1
            self._double_increment()  # Calls another method that needs the lock
    
    def _double_increment(self):
        with self._lock:  # Same thread can acquire RLock again
            self._value += 1
    
    def get_value(self):
        with self._lock:
            return self._value

def rlock_demo():
    print("\n--- RLock Demo ---")
    counter = ThreadSafeCounter()
    
    def worker():
        for _ in range(1000):
            counter.increment()
    
    threads = []
    for i in range(5):
        t = threading.Thread(target=worker)
        threads.append(t)
        t.start()
    
    for t in threads:
        t.join()
    
    print(f"Final counter value: {counter.get_value()}")

# Semaphore example - limiting concurrent access
def semaphore_demo():
    print("\n--- Semaphore Demo ---")
    
    # Allow max 3 concurrent connections to "database"
    db_semaphore = Semaphore(3)
    
    def access_database(worker_id):
        print(f"Worker {worker_id} waiting for database access...")
        
        with db_semaphore:
            print(f"Worker {worker_id} accessing database")
            time.sleep(random.uniform(1, 3))  # Simulate DB operation
            print(f"Worker {worker_id} finished with database")
    
    threads = []
    for i in range(8):
        t = threading.Thread(target=access_database, args=(i,))
        threads.append(t)
        t.start()
    
    for t in threads:
        t.join()

# Event example - signaling between threads
def event_demo():
    print("\n--- Event Demo ---")
    
    data_ready = Event()
    shared_data = []
    
    def producer():
        print("Producer: Generating data...")
        time.sleep(2)
        shared_data.extend([1, 2, 3, 4, 5])
        print("Producer: Data ready!")
        data_ready.set()  # Signal that data is ready
    
    def consumer(consumer_id):
        print(f"Consumer {consumer_id}: Waiting for data...")
        data_ready.wait()  # Wait for the event
        print(f"Consumer {consumer_id}: Processing {shared_data}")
        time.sleep(1)
        print(f"Consumer {consumer_id}: Done")
    
    # Start producer and multiple consumers
    producer_thread = threading.Thread(target=producer)
    consumer_threads = []
    
    for i in range(3):
        t = threading.Thread(target=consumer, args=(i,))
        consumer_threads.append(t)
        t.start()
    
    producer_thread.start()
    
    producer_thread.join()
    for t in consumer_threads:
        t.join()

# Condition example - more complex signaling
def condition_demo():
    print("\n--- Condition Demo ---")
    
    items = []
    condition = Condition()
    
    def consumer():
        with condition:
            while len(items) == 0:
                print("Consumer waiting for items...")
                condition.wait()  # Wait until notified
            item = items.pop(0)
            print(f"Consumer got: {item}")
    
    def producer():
        for i in range(5):
            time.sleep(0.5)
            with condition:
                item = f"item-{i}"
                items.append(item)
                print(f"Producer added: {item}")
                condition.notify()  # Notify one waiting thread
    
    consumer_thread = threading.Thread(target=consumer)
    producer_thread = threading.Thread(target=producer)
    
    consumer_thread.start()
    producer_thread.start()
    
    consumer_thread.join()
    producer_thread.join()


# =============================================================================
# 3. THREAD COMMUNICATION PATTERNS
# =============================================================================

print("\n" + "=" * 60)
print("3. THREAD COMMUNICATION PATTERNS")
print("=" * 60)

# Producer-Consumer with Queue
def producer_consumer_demo():
    print("\n--- Producer-Consumer with Queue ---")
    
    # Thread-safe queue
    task_queue = queue.Queue(maxsize=5)
    result_queue = queue.Queue()
    
    def producer():
        for i in range(10):
            task = f"task-{i}"
            print(f"Producing {task}")
            task_queue.put(task)
            time.sleep(0.1)
        
        # Send sentinel values to stop consumers
        for _ in range(3):
            task_queue.put(None)
    
    def consumer(consumer_id):
        while True:
            task = task_queue.get()
            if task is None:
                task_queue.task_done()
                break
            
            print(f"Consumer {consumer_id} processing {task}")
            time.sleep(0.5)  # Simulate work
            result = f"{task}-processed-by-{consumer_id}"
            result_queue.put(result)
            task_queue.task_done()
    
    # Start threads
    producer_thread = threading.Thread(target=producer)
    consumer_threads = []
    
    for i in range(3):
        t = threading.Thread(target=consumer, args=(i,))
        consumer_threads.append(t)
        t.start()
    
    producer_thread.start()
    producer_thread.join()
    
    for t in consumer_threads:
        t.join()
    
    # Collect results
    print("Results:")
    while not result_queue.empty():
        print(f"  {result_queue.get()}")

# Priority Queue example
def priority_queue_demo():
    print("\n--- Priority Queue Demo ---")
    
    pq = queue.PriorityQueue()
    
    def urgent_task_producer():
        tasks = [
            (1, "CRITICAL: System failure"),
            (3, "LOW: Update documentation"),
            (2, "HIGH: Security patch"),
            (1, "CRITICAL: Data backup"),
            (2, "HIGH: Performance issue")
        ]
        
        for priority, task in tasks:
            pq.put((priority, task))
            print(f"Added: {task} (Priority: {priority})")
            time.sleep(0.2)
    
    def task_processor():
        processed = 0
        while processed < 5:
            priority, task = pq.get()
            print(f"Processing: {task}")
            time.sleep(0.5)
            processed += 1
    
    producer = threading.Thread(target=urgent_task_producer)
    processor = threading.Thread(target=task_processor)
    
    producer.start()
    processor.start()
    
    producer.join()
    processor.join()


# =============================================================================
# 4. ADVANCED PATTERNS AND BEST PRACTICES
# =============================================================================

print("\n" + "=" * 60)
print("4. ADVANCED PATTERNS")
print("=" * 60)

# Thread Pool Pattern (manual implementation)
class ThreadPool:
    def __init__(self, num_threads):
        self.tasks = queue.Queue()
        self.threads = []
        self.shutdown = False
        
        for _ in range(num_threads):
            t = threading.Thread(target=self._worker)
            t.start()
            self.threads.append(t)
    
    def _worker(self):
        while not self.shutdown:
            try:
                task, args, kwargs = self.tasks.get(timeout=1)
                if task is None:
                    break
                task(*args, **kwargs)
                self.tasks.task_done()
            except queue.Empty:
                continue
    
    def submit(self, task, *args, **kwargs):
        if not self.shutdown:
            self.tasks.put((task, args, kwargs))
    
    def close(self):
        self.shutdown = True
        # Add sentinel values
        for _ in self.threads:
            self.tasks.put((None, (), {}))
        
        for t in self.threads:
            t.join()

def threadpool_demo():
    print("\n--- Custom Thread Pool ---")
    
    def work_task(task_id, duration):
        print(f"Task {task_id} starting (duration: {duration}s)")
        time.sleep(duration)
        print(f"Task {task_id} completed")
    
    pool = ThreadPool(3)
    
    # Submit tasks
    for i in range(8):
        pool.submit(work_task, i, random.uniform(0.5, 2))
    
    time.sleep(5)  # Let some tasks complete
    pool.close()
    print("Thread pool closed")

# Using concurrent.futures (preferred approach)
def concurrent_futures_demo():
    print("\n--- Concurrent Futures ---")
    
    def fetch_url(url):
        # Simulate HTTP request
        time.sleep(random.uniform(0.5, 2))
        return f"Content from {url}"
    
    urls = [f"http://api{i}.example.com" for i in range(5)]
    
    # ThreadPoolExecutor
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
        # Submit all tasks
        future_to_url = {executor.submit(fetch_url, url): url for url in urls}
        
        # Process results as they complete
        for future in concurrent.futures.as_completed(future_to_url):
            url = future_to_url[future]
            try:
                result = future.result()
                print(f"✓ {url}: {result}")
            except Exception as exc:
                print(f"✗ {url} generated exception: {exc}")

# Thread-local storage
thread_local = threading.local()

def process_request(user_id):
    # Each thread gets its own copy of thread_local
    thread_local.user_id = user_id
    thread_local.request_count = 0
    
    for i in range(3):
        handle_subrequest()

def handle_subrequest():
    thread_local.request_count += 1
    print(f"User {thread_local.user_id}: Subrequest #{thread_local.request_count}")
    time.sleep(0.1)

def thread_local_demo():
    print("\n--- Thread Local Storage ---")
    
    threads = []
    for user_id in range(3):
        t = threading.Thread(target=process_request, args=(user_id,))
        threads.append(t)
        t.start()
    
    for t in threads:
        t.join()

# Barrier synchronization
def barrier_demo():
    print("\n--- Barrier Synchronization ---")
    
    barrier = Barrier(3)  # Wait for 3 threads
    
    def worker(worker_id):
        # Phase 1: Preparation
        prep_time = random.uniform(1, 3)
        print(f"Worker {worker_id}: Preparing for {prep_time:.1f}s...")
        time.sleep(prep_time)
        print(f"Worker {worker_id}: Ready for synchronization")
        
        # Synchronization point
        barrier.wait()
        
        # Phase 2: Coordinated work
        print(f"Worker {worker_id}: Starting coordinated work")
        time.sleep(1)
        print(f"Worker {worker_id}: Coordinated work complete")
    
    threads = []
    for i in range(3):
        t = threading.Thread(target=worker, args=(i,))
        threads.append(t)
        t.start()
    
    for t in threads:
        t.join()


# =============================================================================
# 5. COMMON PITFALLS AND DEBUGGING
# =============================================================================

print("\n" + "=" * 60)
print("5. COMMON PITFALLS AND DEBUGGING")
print("=" * 60)

# Deadlock example and solution
def deadlock_demo():
    print("\n--- Deadlock Prevention ---")
    
    lock1 = Lock()
    lock2 = Lock()
    
    def task1():
        print("Task 1: Acquiring lock1...")
        with lock1:
            print("Task 1: Got lock1, waiting for lock2...")
            time.sleep(0.1)
            with lock2:  # This could cause deadlock
                print("Task 1: Got both locks")
    
    def task2():
        print("Task 2: Acquiring lock2...")
        with lock2:
            print("Task 2: Got lock2, waiting for lock1...")
            time.sleep(0.1)
            with lock1:  # This could cause deadlock
                print("Task 2: Got both locks")
    
    # This might deadlock (don't run in production)
    # Uncomment to see deadlock:
    # t1 = threading.Thread(target=task1)
    # t2 = threading.Thread(target=task2)
    # t1.start()
    # t2.start()
    # t1.join()
    # t2.join()
    
    print("Deadlock demo skipped (would hang). Use consistent lock ordering to prevent.")

# Proper exception handling in threads
def exception_handling_demo():
    print("\n--- Exception Handling in Threads ---")
    
    def risky_task(task_id):
        try:
            if task_id == 2:
                raise ValueError(f"Simulated error in task {task_id}")
            print(f"Task {task_id}: Success")
            return f"Result {task_id}"
        except Exception as e:
            print(f"Task {task_id}: Exception - {e}")
            raise  # Re-raise to be caught by executor
    
    with concurrent.futures.ThreadPoolExecutor() as executor:
        futures = [executor.submit(risky_task, i) for i in range(5)]
        
        for i, future in enumerate(futures):
            try:
                result = future.result()
                print(f"Got result: {result}")
            except Exception as e:
                print(f"Task {i} failed with: {e}")

# Graceful shutdown pattern
class GracefulService:
    def __init__(self):
        self.shutdown_event = threading.Event()
        self.workers = []
    
    def worker(self, worker_id):
        while not self.shutdown_event.is_set():
            try:
                # Do work with timeout to check shutdown
                print(f"Worker {worker_id}: Working...")
                if self.shutdown_event.wait(timeout=2):  # Check every 2 seconds
                    break
            except Exception as e:
                print(f"Worker {worker_id}: Error - {e}")
        
        print(f"Worker {worker_id}: Shutting down gracefully")
    
    def start(self, num_workers=3):
        for i in range(num_workers):
            t = threading.Thread(target=self.worker, args=(i,))
            t.start()
            self.workers.append(t)
        print(f"Service started with {num_workers} workers")
    
    def stop(self):
        print("Initiating graceful shutdown...")
        self.shutdown_event.set()
        
        for t in self.workers:
            t.join()
        
        print("Service stopped gracefully")

def graceful_shutdown_demo():
    print("\n--- Graceful Shutdown ---")
    
    service = GracefulService()
    service.start()
    
    # Let it run for a bit
    time.sleep(5)
    
    # Shutdown gracefully
    service.stop()


# =============================================================================
# 6. PERFORMANCE CONSIDERATIONS AND MONITORING
# =============================================================================

print("\n" + "=" * 60)
print("6. PERFORMANCE MONITORING")
print("=" * 60)

def performance_comparison():
    print("\n--- Performance Comparison ---")
    
    def cpu_intensive_work(n):
        return sum(i * i for i in range(n))
    
    def io_intensive_work():
        time.sleep(0.1)  # Simulate I/O
        return "IO complete"
    
    # Test CPU-bound tasks (GIL limited)
    print("CPU-bound tasks:")
    start = time.time()
    results = [cpu_intensive_work(100000) for _ in range(4)]
    sequential_time = time.time() - start
    print(f"Sequential: {sequential_time:.3f}s")
    
    start = time.time()
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
        results = list(executor.map(cpu_intensive_work, [100000] * 4))
    threaded_time = time.time() - start
    print(f"Threaded: {threaded_time:.3f}s")
    print(f"Speedup: {sequential_time/threaded_time:.2f}x")
    
    # Test I/O-bound tasks
    print("\nI/O-bound tasks:")
    start = time.time()
    results = [io_intensive_work() for _ in range(10)]
    sequential_time = time.time() - start
    print(f"Sequential: {sequential_time:.3f}s")
    
    start = time.time()
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        results = list(executor.map(lambda x: io_intensive_work(), range(10)))
    threaded_time = time.time() - start
    print(f"Threaded: {threaded_time:.3f}s")
    print(f"Speedup: {sequential_time/threaded_time:.2f}x")

# Thread monitoring
def thread_monitoring_demo():
    print("\n--- Thread Monitoring ---")
    
    def monitor_threads():
        while True:
            active = threading.active_count()
            current = threading.current_thread()
            all_threads = threading.enumerate()
            
            print(f"Active threads: {active}")
            print(f"Current thread: {current.name}")
            print("All threads:")
            for t in all_threads:
                print(f"  - {t.name} ({'alive' if t.is_alive() else 'dead'})")
            
            time.sleep(2)
            if active <= 2:  # Only main and monitor threads
                break
    
    # Start monitoring
    monitor_thread = threading.Thread(target=monitor_threads, name="Monitor")
    monitor_thread.start()
    
    # Create some worker threads
    def worker(name, duration):
        time.sleep(duration)
    
    workers = []
    for i in range(3):
        t = threading.Thread(target=worker, args=(f"Worker-{i}", 3), name=f"Worker-{i}")
        workers.append(t)
        t.start()
    
    for t in workers:
        t.join()
    
    monitor_thread.join()


# =============================================================================
# MAIN EXECUTION
# =============================================================================

if __name__ == "__main__":
    print("Python Threading Tutorial - Advanced Level")
    print("=========================================")
    
    try:
        # Run all examples
        basic_threading_example()
        custom_thread_example()
        
        race_condition_demo()
        lock_demo()
        rlock_demo()
        semaphore_demo()
        event_demo()
        condition_demo()
        
        producer_consumer_demo()
        priority_queue_demo()
        
        threadpool_demo()
        concurrent_futures_demo()
        thread_local_demo()
        barrier_demo()
        
        deadlock_demo()
        exception_handling_demo()
        graceful_shutdown_demo()
        
        performance_comparison()
        thread_monitoring_demo()
        
    except KeyboardInterrupt:
        print("\nDemo interrupted by user")
    except Exception as e:
        print(f"Demo error: {e}")
    
    print("\n" + "=" * 60)
    print("TUTORIAL COMPLETE")
    print("=" * 60)
    print("""
Key Takeaways:
1. Use threads for I/O-bound tasks, not CPU-bound (due to GIL)
2. Always use proper synchronization (locks, queues, etc.)
3. Prefer concurrent.futures over manual thread management
4. Handle exceptions properly in threaded code
5. Implement graceful shutdown mechanisms
6. Monitor thread usage and performance
7. Avoid deadlocks with consistent lock ordering
8. Use thread-local storage for per-thread data
    """)