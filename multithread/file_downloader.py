import threading
import time
import concurrent
import requests

links = [
  "https://stackoverflow.com/questions/919897/how-to-obtain-a-thread-id-in-python",
  "https://www.tutorialspoint.com/python/python_naming_thread.htm",
  "https://superfastpython.com/threadpoolexecutor-thread-names-2/"
]
# same header across all session
session = requests.Session()
session.headers.update({'x-test': 'true','Accept': 'application/json'})


# def download_webpage(link,results,delay=3):
#   time.sleep(delay)
#   print(f"Downloading : {link[:20]} ...")
#   response = session.get(link)
#   print(response.status_code)
#   print("-------------------------")
#   results.append(response.text)
  
# threads = []
# results = []
# for i in range(3):
#   t = threading.Thread(target=download_webpage,args=(links[i],results,),kwargs={"delay":2})
#   threads.append(t)
#   t.start()

# for t in threads:
#   t.join()


  
from concurrent.futures import ThreadPoolExecutor,as_completed

session = requests.Session()
session.headers.update({
    'User-Agent': 'ScriptDownloader/1.0 (Windows; Python 3.x)',
})

file_links = [
    {"url": "https://en.wikipedia.org/wiki/British_logistics_in_the_Normandy_campaign", "filename": r"i:\wfile1"},
    {"url": "https://en.wikipedia.org/wiki/Graph_(abstract_data_type)", "filename": r"i:\Graph_abstract_data_type"},
    {"url": "https://example.com/", "filename": r"i:\example"}
]

def download_webpage(file_link,delay=3):
  time.sleep(delay)
  print(f"Downloading : {file_link["url"][:20]} ...")
  response = session.get(file_link["url"],params=file_link["filename"])
  print(response.status_code)
  print("-------------------------")
  return response.text

results = []

with ThreadPoolExecutor(max_workers=2) as executor:
  
  # results = list(executor.map(lambda li:download_webpage(li,2),file_links))
  futures = {
        executor.submit(download_webpage, link, delay=2): link for link in file_links
    }
  for future_obj in as_completed(futures):
    req_id = futures[future_obj]
    result = future_obj.result()
    print(f"Request {req_id}: {result[:200]}")



# print("===================")
# for result in results:
#   print(result[:200])
#   print("===================")