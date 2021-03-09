# container-migration
Instructions and tools to manage the life cycle of runC containers and migrate them between hosts.


## Step 1 - Device images

From this [link](https://unipiit-my.sharepoint.com/:f:/g/personal/a035017_unipi_it/EitRqDdu7ElHgdQolR8L460BlMvDN-z6fpKHW5Xe77ncPA?e=gEVxbC), you can download image files of different devices that are fully configured to run containers and migrate them. Install these images to a couple of devices that you own to be ready for the next step. We currently provide the images of two devices:


1. A **Raspberry Pi 3 Model B** with Debian 9.5 (Linux kernel 4.14). Username/password => pi/raspberry
2. A **QEMU virtual machine** with Ubuntu 18.04 (Linux kernel 4.19) -- coming soon. Username/password => ubuntu/ubuntu


Both the images include the following tools, which are necessary to run and migrate runC containers:


1. **CRIU** (version 3.10 for the Raspberry; version 3.11 for the virtual machine). CRIU is used to checkpoint the container state on the source device and restore the state on the destination one. Some Linux kernel options must be enabled for CRIU to work (https://criu.org/Linux_kernel). We enabled all the required options for you and compiled the kernels of both images
2. **rsync** (version 3.1.2). This is used to copy the container state from the source device to the destination one. rsync can use ssh for secure transfers, can compress data, and can perform incremental transfers.
3. **runC** (version 1.0.1 for the Raspberry; version 1.0.0 for the virtual machine). runC is an OCI-compliant container runtime. For more information, refer to https://github.com/opencontainers/runc
4. **skopeo** (version 1.2.2). This is a tool that you can use to, e.g., copy Docker images from Docker Hub and convert them to OCI images, i.e., base images of runC containers (https://github.com/containers/skopeo)
5. **umoci** (version 0.4.6). This utility allows to, e.g., unpack an OCI image to an OCI bundle, which is the container filesystem (https://github.com/opencontainers/umoci)
6. **hostapd** (version 2.4) and **dnsmasq** (version 2.76), only for Raspberry. We installed and configured these tools on the Raspberry to let it expose a Wi-Fi access point. The SSID is "AP1" and the password is "fogcomputing"


## Step 2 - Create an OCI bundle

In order to launch a runC container, you first need to create an OCI bundle. One way to do this is as follows:


1. Firstly, go to the Docker Hub (https://hub.docker.com/) and choose a Docker image
2. Next, use the ***skopeo copy*** command to download the Docker image and convert it to an OCI image that is located in your local OCI directory
3. Then, create a **/runc/containers/** directory where you will locate all your OCI bundles
4. Finally, use the ***umoci unpack*** command to unpack your OCI image to an OCI bundle located in /runc/containers/, e.g., /runc/containers/bundle-name


## Step 3 - Configure passwordless ssh access [optional]   

Next step is setting up passwordless ssh login from root@source to root@destination. On the source device, type:

  `sudo ssh-keygen`

Opt for "no passphrase". By default, you will find a *id_rsa/id_rsa.pub* key pair in */root/.ssh/*. Then, copy the **content** of the *id_rsa.pub* public key at the end of the */root/.ssh/authorized_keys* file at the destination device.


## Step 4 - Configure tc-netem and tc-htb [optional]

Both the images described in Step 1 have Linux traffic control (tc) installed. Linux tc is a useful set of tools for managing and manipulating the transmission of packets, e.g., during container migration. Specifically, *tc-netem* allows to add delay, packet loss, duplication, etc ... while *tc-htb* allows to control the use of the outbound bandwidth on a given link. You may want to use these tools to emulate certain network conditions between the source and the destination devices. For example, you may type the following commands (only on the source device):

  `sudo tc qdisc add dev eth0 root handle 1: htb`  

  `sudo tc class add dev eth0 parent 1: classid 1:1 htb rate 20mbit`

  `sudo tc filter add dev eth0 protocol ip parent 1:0 prio 1 u32 match ip dst 192.168.1.2 flowid 1:1`

  `sudo tc qdisc add dev eth0 parent 1:1 handle 10: netem delay 80ms`

This simple example sets a 20 Mbps rate and a fixed delay of 80 ms for all packets exiting the eth0 interface on the source device and directed towards IP address 192.168.1.2.


## Step 5 - Run and migrate the container
 
