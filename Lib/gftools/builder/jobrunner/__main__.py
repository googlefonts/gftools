import subprocess
import sys

# A big problem with ninja is that because it runs multiple jobs at once,
# the output of failing jobs is mixed up with the output of successful jobs.
# Multiple successful short jobs can run while a big job is failing, meaning
# that when you look at the end of the log file to work out what went
# wrong you

if __name__ == "__main__":
    cmd = " ".join(sys.argv[1:])
    result = subprocess.run(sys.argv[1:], capture_output=True)
    if result.returncode != 0:
        print("\nCommand failed:\n" + cmd)
        print(result.stdout.decode())
        print(result.stderr.decode())
    else:
        print(cmd)
    sys.exit(result.returncode)
