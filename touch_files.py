import os
import time

print("Updating file timestamps...")
count = 0
errors = 0
for root, dirs, files in os.walk("."):
    # Skip .git directory manually if os.walk goes into it (though we usually want to touch source files)
    if ".git" in root:
        continue
        
    for f in files:
        path = os.path.join(root, f)
        try:
            os.utime(path, None)
            count += 1
        except Exception as e:
            # print(f"Skipped {path}: {e}")
            errors += 1
print(f"Touched {count} files. Errors: {errors}")
