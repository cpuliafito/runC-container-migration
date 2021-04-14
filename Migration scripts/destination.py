#!/usr/bin/env python
#code retrieved from https://www.redhat.com/en/blog/container-migration-around-world and partially modified
import socket
import sys
from thread import *
import json
import os
import distutils.util
import subprocess

def migrate_server():
    HOST = ''   # Symbolic name meaning all available interfaces
    PORT = 18863

    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    print 'Socket created'

    #Bind socket to local host and port
    try:
        s.bind((HOST, PORT))
    except socket.error as msg:
        print 'Bind failed. Error Code : ' + str(msg[0]) + ' Message ' + msg[1]
        sys.exit()

    print 'Socket bind complete'

    #Start listening on socket
    s.listen(10)
    print 'Socket now listening'

    #Function for handling connections. This will be used to create threads
    def clientthread(conn, addr):
        #Sending message to connected client

        #infinite loop so that function does not terminate and thread does not end.
        while True:

            reply = ""
            #Receiving from client
            data = conn.recv(1024)
            if not data:
                break
            if data == 'exit':
                break

            try:
                #Parse JSON string into Python dictionary
                msg = json.loads(data)
                if 'restore' in msg:

                    os.system('criu -V')

                    try:
                        lazy = bool(distutils.util.strtobool(msg['restore']['lazy']))
                    except:
                        lazy = False

                    old_cwd = os.getcwd()
                    os.chdir(msg['restore']['path'])
                    #The following command is the restore command, which resotres execution of the container at destination
                    cmd = 'time -p runc restore --console-socket ' + msg['restore']['path']
                    cmd += '/console.sock -d --image-path ' + msg['restore']['image_path']
                    cmd += ' --work-path ' + msg['restore']['image_path']
                    #In case of a post-copy phase in the migration technique, the restore command restores the process without filling out the entire memory contents.
                    #When the --lazy-pages option is used, restore registers the lazy virtual memory areas (VMAs) with the userfaultfd mechanism. The lazy pages are completely handled by dedicated lazy-pages daemon.
                    #The daemon receives userfault file descriptors from restore via UNIX socket.
                    if lazy:
                            cmd += ' --lazy-pages'
                    cmd += ' ' + msg['restore']['name']
                    print "Running " +  cmd
                    p = subprocess.Popen(cmd, shell=True)
                    #This new command starts the lazy-pages daemon. The daemon monitors the UFFD events and repopulates the tasks address space by requesting lazy pages to the page server running on the source.

                    #Please, read https://criu.org/CLI/opt/--lazy-pages and https://criu.org/Userfaultfd for more information.

                    #The daemon tracks and prints the flow of time and clearly prints when it starts requesting faulted pages and when it finishes, along with an indication of the number of transferred faulted pages.
                    #Note that each page is 4KB.
                    if lazy:
                        cmd = "criu lazy-pages --page-server --address " + addr
                        cmd += " --port 27 -vv -D "
                        cmd += msg['restore']['image_path']
                        cmd += " -W "
                        cmd += msg['restore']['image_path']
                        print "Running lazy-pages server: " + cmd
                        lp = subprocess.Popen(cmd, shell=True)
                    ret = p.wait()
                    if ret == 0:
                        reply = "runc restored %s successfully" % msg['restore']['name']
                    else:
                        reply = "runc failed(%d)" % ret
                    os.chdir(old_cwd)
                else:
                    print "Unkown request : " + msg
            except:
                continue

            print reply
            conn.sendall(reply)

        #came out of loop
        conn.close()

    #now keep talking with the client
    while 1:
        #wait to accept a connection - blocking call
        conn, addr = s.accept()
        print 'Connected with ' + addr[0] + ':' + str(addr[1])

        #start new thread takes 1st argument as a function name to be run, second is the tuple of arguments to the function.
        start_new_thread(clientthread ,(conn, str(addr[0]),))

    s.close()

if __name__ == '__main__':
    migrate_server()
