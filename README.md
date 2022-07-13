# Migrate runC containers between hosts
Instructions and tools to manage the life cycle of runC containers and migrate them between hosts.

If you find this work useful in your research, please cite:

C. Puliafito, C. Vallati, E. Mingozzi, G. Merlino, F. Longo, “Design and evaluation of a fog platform supporting device mobility through container migration”, Elsevier Pervasive and Mobile Computing, vol. 74, Jul. 2021, doi: https://doi.org/10.1016/j.pmcj.2021.101415


## Step 1 - Device images

From this [link](https://unipiit-my.sharepoint.com/:f:/g/personal/a035017_unipi_it/EitRqDdu7ElHgdQolR8L460BlMvDN-z6fpKHW5Xe77ncPA?e=gEVxbC), you can download image files of different devices that are fully configured to run containers and migrate them. Install these images to a couple of hosts that you own to be ready for the next step. We currently provide the images of two devices:


1. A **Raspberry Pi 3 Model B** with Debian 9.5 (Linux kernel 4.14). Username/password => pi/raspberry
2. A **QEMU virtual machine** with Ubuntu 18.04 (Linux kernel 4.19) -- coming soon. Username/password => ubuntu/ubuntu


Both the images include the following tools, which are needed to run and migrate runC containers:


1. **CRIU** (version 3.10 for the Raspberry; version 3.11 for the virtual machine). CRIU is used to checkpoint the container state on the source host and restore the state on the destination one. Some Linux kernel options must be enabled for CRIU to work (https://criu.org/Linux_kernel). We enabled all the required options for you and compiled the kernels of both images
2. **rsync** (version 3.1.2). This is used to copy the container state from the source host to the destination one. rsync can use ssh for secure transfers, can compress data, and can perform incremental transfers.
3. **runC** (version 1.0.1 for the Raspberry; version 1.0.0 for the virtual machine). runC is an OCI-compliant container runtime. For more information, refer to https://github.com/opencontainers/runc
4. **skopeo** (version 1.2.2). This is a tool that you can use to, e.g., copy Docker images from Docker Hub and convert them to OCI images, i.e., base images of runC containers (https://github.com/containers/skopeo)
5. **umoci** (version 0.4.6). This utility allows to, e.g., unpack an OCI image to an OCI bundle, which is the container filesystem (https://github.com/opencontainers/umoci)
6. **hostapd** (version 2.4) and **dnsmasq** (version 2.76), only for Raspberry. We installed and configured these tools on the Raspberry to let it expose a Wi-Fi access point. The SSID is "AP1" and the password is "fogcomputing"


Before going to the next step, you need to copy the **Migration scripts** from this repository to the source and the destination hosts.


## Step 2 - Create an OCI bundle

In order to run a runC container, you first need to create an OCI bundle. One way to do this is as follows:


1. Firstly, go to the Docker Hub (https://hub.docker.com/) and choose a Docker image
2. Next, use the ***skopeo copy*** command to download the Docker image and convert it to an OCI image that is located in your local OCI directory
3. Then, create a **/runc/containers/** directory where you will locate all your OCI bundles
4. Finally, use the ***umoci unpack*** command to unpack your OCI image to an OCI bundle located in /runc/containers/, e.g., /runc/containers/bundle-name


You can perform the previous steps, for instance, on the source host and then copy the OCI bundle under the same path on the destination host.


## Step 3 - Configure passwordless ssh access [optional]   

Next step is setting up passwordless ssh login from root@source to root@destination. This avoids you to manually insert the password when using rsync to copy the container state from source to destination host. On the source host, type:

  `sudo ssh-keygen`

Opt for "no passphrase". By default, you will find a *id_rsa/id_rsa.pub* key pair in */root/.ssh/*. Then, copy the **content** of the *id_rsa.pub* public key at the end of the */root/.ssh/authorized_keys* file at the destination host.


## Step 4 - Configure tc-netem and tc-htb [optional]

Both the images described in Step 1 have Linux traffic control (tc) installed. Linux tc is a useful set of tools for managing and manipulating the transmission of packets, e.g., during container migration. Specifically, *tc-netem* allows to add delay, packet loss, duplication, etc ... while *tc-htb* allows to control the use of the outbound bandwidth on a given link. You may want to use these tools to emulate certain network conditions between the source and the destination hosts. For example, you may type the following commands (only on the source host):

  `sudo tc qdisc add dev eth0 root handle 1: htb`  

  `sudo tc class add dev eth0 parent 1: classid 1:1 htb rate 20mbit`

  `sudo tc filter add dev eth0 protocol ip parent 1:0 prio 1 u32 match ip dst 192.168.1.2 flowid 1:1`

  `sudo tc qdisc add dev eth0 parent 1:1 handle 10: netem delay 80ms`

This simple example sets a 20 Mbps rate and a fixed delay of 80 ms for all packets exiting the eth0 interface on the source host and directed towards IP address 192.168.1.2.


## Step 5 - Run and migrate the container

### On the destination host

Run the following command to create a Unix domain socket. This is needed to let the container run in **detached new terminal** mode -- see [here](https://github.com/opencontainers/runc/blob/master/docs/terminals.md) for more information.

  `sudo recvtty -m null /runc/containers/name-of-your-bundle/console.sock`

Then, move to the location of the migration scripts and run the destination script with the following command:

  `sudo python ./destination.py`


### On the source host

Create a Unix domain socket with the same command as for the destination host:

  `sudo recvtty -m null /runc/containers/name-of-your-bundle/console.sock`

Run the runC container in detached new terminal mode. **container-name MUST be the same as name-of-you-bundle**:

  `sudo runc run --console-socket /runc/containers/name-of-your-bundle/console.sock -d -b /runc/containers/name-of-your-bundle container-name`

Type the following command to check if the container is running:

  `sudo runc list`

Now, it is time to migrate the container to the destination host. To this purpose, move to the location of the migration scripts and run the source script as follows:

  `sudo python ./source.py container-name destination-ip Pre Lazy`

where *container-name* is the name of the container and *destination-ip* is the IP address of the destination host.
*Pre* and *Lazy* are two flags that let you decide which technique to use for stateful container migration. The four main techniques are available, which are:

1. Cold Migration (Pre=**False** and Lazy=**False**)
2. Pre-copy Migration (Pre=**True** and Lazy=**False**)
3. Post-copy Migration (Pre=**False** and Lazy=**True**)
4. Hybrid Migration (Pre=**True** and Lazy=**True**)

More details on the container migration techniques can be found in [1].


### On both the source and destination hosts

Read the migration results (i.e., times to complete each task; sizes of data being checkpointed and transferred) returned by the scripts.

If you type:

  `sudo runc list`

on the destination host, you should see the container running. The same command on the source host will return an empty list.


### On the destination host

Before performing a new experiment run, you need to execute the following commands on the destination host. First, kill the container with:

  `sudo runc kill container-name KILL`

Then, delete the container with:

  `sudo runc delete container-name`

Finally, remove the */image* and */parent* directories from the container bundle, which respectively contain the results of dump and pre-dump (if any):  

  `sudo rm -rf /runc/containers/name-of-your-bundle/image`
  `sudo rm -rf /runc/containers/name-of-your-bundle/parent`


## References

[1] C. Puliafito, C. Vallati, E. Mingozzi, G. Merlino, F. Longo, A. Puliafito, "Container Migration in the Fog: A Performance Evaluation" MDPI Sensors, 19(7): 1488, 2019. doi: https://doi.org/10.3390/s19071488

[2] C. Puliafito, C. Vallati, E. Mingozzi, G. Merlino, F. Longo, “Design and evaluation of a fog platform supporting device mobility through container migration”, Elsevier Pervasive and Mobile Computing, vol. 74, Jul. 2021, doi: https://doi.org/10.1016/j.pmcj.2021.101415