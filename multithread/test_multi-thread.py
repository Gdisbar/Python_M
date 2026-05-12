import threading
import sys
import traceback

def dump_threads():
    # Get all current stack frames once to avoid dictionary size changes during iteration
    frames = sys._current_frames()
    
    for th in threading.enumerate():
        print(f"\n--- Thread {th.name} (id={th.ident}) ---")
        
        # Safely get the frame for this thread ID
        frame = frames.get(th.ident)
        
        if frame:
            for line in traceback.format_stack(frame):
                print(line.strip())
        else:
            print("  [No stack frame available for this thread]")

if __name__ == "__main__":
    dump_threads()