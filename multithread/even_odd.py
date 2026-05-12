import threading
from concurrent.futures import ThreadPoolExecutor,as_completed

def find_even_odd(start,end):
    evens = [n for n in range(start, end + 1) if n % 2 == 0]
    odds = [n for n in range(start, end + 1) if n % 2 != 0]
    return {"even": evens, "odd": odds}

with ThreadPoolExecutor(max_workers=2) as executor:
    # futures = executor.submit(find_even_odd,30,50)
    # results = futures.result()
    ## Each argument must be a list or iterable 
    futures = executor.map(find_even_odd, [30], [50])
    results = list(futures)
    
print(results)


rlock = threading.RLock()

def fact_func(n):
    with rlock:
        if n<1: return 1
        return n * fact_func(n-1)

with ThreadPoolExecutor(max_workers=1) as executor:
    future = executor.submit(fact_func,5)    
    result = future.result()
print(f"n(=5)! = {result}")
