#!/usr/bin/env python
#code retrieved from https://www.redhat.com/en/blog/container-migration-around-world and partially modified
import socket
import sys
import select
import time
import os
import shutil
import subprocess
import distutils.util


def error():
    print "Something did not work. Exiting!"
    sys.exit(1)


#Prepare for migration.
#Delete the entire directory tree for both image and parent (which could be present from previous migrations)
def prepare(image_path, parent_path):
    try:
        shutil.rmtree(image_path)
    except:
        pass
    try:
        shutil.rmtree(parent_path)
    except:
        pass

#create the pre-dump, which is done in case of pre-copy and hybrid migrations.
#pre-dump contains the entire content of the container virtual memory
#pre-dump is stored in the parent directory
def pre_dump(base_path, container):
    old_cwd = os.getcwd()
    os.chdir(base_path)
    cmd = 'time -p runc checkpoint --pre-dump --image-path parent'
    cmd += ' ' + container
    print cmd   #!
    #start = time.time()
    ret = os.system(cmd)
    #end = time.time()
    #print "%s finished after %d second(s) with %d" % (cmd, end - start, ret)
    os.chdir(old_cwd)
    if ret != 0:
        error()

#create the dump. This is done for any migration technique. Content of the dump varies depending on the technique.
#dump is stored in the image directory.
#in case of pre-dump present, specify it is in the parent directory.
#When post-copy phase is not present, wait until dump command ends (with p.wait())
#If instead post-copy phase is present, the dump procedure does not write memory pages in image and starts the page server for later transfer of faulted pages.
#the page server will then read local memory dump and send memory pages upon request of the lazy-pages daemon running on the destination.
#The page server listens on port 27.
#Still in case of the post-copy phase, with the --status-fd option, CRIU writes '\0' to the specified pipe when it has finished with the checkpoint and start of the page server

#Read https://criu.org/CLI/opt/--lazy-pages and https://criu.org/CLI/opt/--status-fd for more information.
def real_dump(precopy, postcopy):
    old_cwd = os.getcwd()
    os.chdir(base_path)
    cmd = 'time -p runc checkpoint --image-path image --leave-running'
    cmd = 'time -p runc checkpoint --image-path image'
    if precopy:
        cmd += ' --parent-path ../parent'
    if postcopy:
        cmd += ' --lazy-pages'
        cmd += ' --page-server localhost:27'
        try:
            os.unlink('/tmp/postcopy-pipe')
        except:
            pass
        os.mkfifo('/tmp/postcopy-pipe')
        cmd += ' --status-fd /tmp/postcopy-pipe'
    cmd += ' ' + container
    start = time.time()
    print cmd
    p = subprocess.Popen(cmd, shell=True)
    if postcopy:
        p_pipe = os.open('/tmp/postcopy-pipe', os.O_RDONLY)
        ret = os.read(p_pipe, 1)
        if ret == '\0':
            print 'Ready for lazy page transfer'
        ret = 0
    else:
        ret = p.wait()

    end = time.time()
    print "%s finished after %.2f second(s) with %d" % (cmd, end - start, ret)
    os.chdir(old_cwd)
    if ret != 0:
        error()

#Transfer the previously created pre-dump using rsync
def xfer_pre_dump(parent_path, dest, base_path):
    sys.stdout.write('PRE-DUMP size: ')
    sys.stdout.flush()
    cmd = 'du -hs %s' % parent_path
    ret = os.system(cmd)
    cmd = 'time -p rsync %s --stats %s %s:%s/' % (rsync_opts, parent_path, dest, base_path)
    print "Transferring PRE-DUMP to %s" % dest
    #start = time.time()
    ret = os.system(cmd)
    #end = time.time()
    #print "PRE-DUMP transfer time %s seconds" % (end - start)
    if ret != 0:
        error()

#Transfer the previosuly created dump using rsync
def xfer_final(image_path, dest, base_path):
    sys.stdout.write('DUMP size: ')
    sys.stdout.flush()
    cmd = 'du -hs %s' % image_path
    ret = os.system(cmd)
    cmd = 'time -p rsync %s --stats %s %s:%s/' % (rsync_opts, image_path, dest, base_path)
    print "Transferring DUMP to %s" % dest
    #start = time.time()
    ret = os.system(cmd)
    #end = time.time()
    #print "DUMP transfer time %s seconds" % (end - start)
    if ret != 0:
        error()

def touch(fname):
    open(fname, 'a').close()


def migrate(container, dest, pre, lazy):
    base_path = runc_base + container
    image_path = base_path + "/image"
    parent_path = base_path + "/parent"

    prepare(image_path, parent_path)
    if pre:
        pre_dump(base_path, container)
        xfer_pre_dump(parent_path, dest, base_path)
    real_dump(pre, lazy)
    xfer_final(image_path, dest, base_path)

    cs = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    #Connect to the migration server running on the destination to send the restore command
    cs.connect((dest, 18863))

    input = [cs,sys.stdin]

    #send the restore command
    cs.send('{ "restore" : { "path" : "' + base_path + '", "name" : "' + container + '" , "image_path" : "' + image_path + '" , "lazy" : "' + str(lazy) + '" } }')

    while True:
        #select.select calls the Unix select() system call
        #the first three arguments are three waitable objects (a read list, a write list, and an exception list). The fourth argument is a timeout
        #After the timeout, select() returns the triple of lists of objects that are ready (subset of the three arguments)... or empty if not ready
        inputready, outputready, exceptready = select.select(input,[],[], 5)

        #If after 5 seconds there is nothing to read, then exit
        if not inputready:
            break

        #If there is something in input to read (e.g., from the socket), then print it
        for s in inputready:
             answer = s.recv(1024)
             print answer

    return True


if __name__ == '__main__':

    runc_base = "/runc/containers/"

    lazy = False
    pre = False


    #The name of the container is the first argument
    #NOTE: for the way the code is currently written, it must be the same as the name of the OCI bundle
    container = sys.argv[1]
    #destination IP is the second argument
    dest = sys.argv[2]
    #Third and fourth arguments are respectively the Pre and Lazy flags, which are used to determine the migration techniques as follows:
    #Cold = False False
    #Pre-copy = True False
    #Post-copy = False True
    #Hybrid = True True
    if len(sys.argv) > 3:
        pre = distutils.util.strtobool(sys.argv[3])
    if len(sys.argv) > 4:
        lazy = distutils.util.strtobool(sys.argv[4])

    base_path = runc_base + container
    image_path = base_path + "/image"
    parent_path = base_path + "/parent"

    #-h outputs numbers in human readable format
    #-a enables archive mode, which preserves permissions, ownership, and modification times, among other things
    #-z enables compression during transfer
    rsync_opts = "-haz"

    migrate(container, dest, pre, lazy)
