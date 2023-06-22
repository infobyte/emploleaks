import os
import sys

print("Running Python script {!r} which was called with {} arguments".format(os.path.basename(sys.argv[0]), len(sys.argv) - 1))
for i, arg in enumerate(sys.argv[1:]):
    print("arg {}: {!r}".format(i + 1, arg))

#TODO: agregar --output greap a linkedin para postprocesarlo con los workflows
import pdb;pdb.set_trace()
