# farsight

farsight is a client/server application that allows users to implement block devices
without the need for kernel modules by extending a very simple interface.

# usage

As with most python packages, it suffices to call the setup script:

```shell
python3 setup.py install
```

Afterwards, we may use the client and server modules within the 'farsight' package.
First, we need to provide configuration files for both. The chosen format is TOML,
because of its simplicity and portability.

## configuring the client
The client must specify the sections: "nbd", "server" and "backend".

### NBD parameters
These are low-level parameters to use in the underlying NBD protocol. This section
is currently comprised of 2 parameters: "file" and "blocksize".

The "file" parameter specifies which of the "/dev/nbd" block devices should be
bound to a backing storage (described later in this document). The device must
not be in use at the time the client is started.

The "blocksize" parameter indicates the size in bytes of the block for the device,
as the Linux kernel would see it. The kernel performs operations within the block
device in units of this size. (Note, however, that across the network, the kernel
always uses a page for granularity).

### server parameters
This section specifies the needed parameters to connect to a server. Namely, the
"address" and "port" keys are used to uniquely identify the server. We support
both IPv4 and IPv6 addresses.

### backend parameters
This section describes which backend will be used by the server to back a
block device. Each backend has its own set of parameters, described later in
this document. The only required parameter is "name" which is read by the
server to determine which of the supported backends will be used.

## configuring the server
The server must define the aptly named "server" section which will define the
address and port where it will listen for connections, and it should have one
section per supported backend.

### server parameters
In addition to the "address" and "port" parameters which define where the
server will be listening for incoming clients, there's an additional parameter
called "max_errors", which specifies how many invalid requests per client the
server will tolerate before disconnecting said client.

## backend configuration
By themselves, the client and server don't do much unless they agree on a
backend to use. At the time of this writing, farsight only supports the
"rbd" backend, which needs to be configured by both the client and server.

### rbd dependencies
In order to use the RBD backend, the server must have the necessary libraries
included. They can be installed by the system's package manager. For example,
on Ubuntu, you may run something like this:

```shell
apt install python3-rados python3-rbd
```

For more information, see here:
<https://docs.ceph.com/en/latest/rados/api/python/>
<https://docs.ceph.com/en/latest/rbd/api/librbdpy/>

Note that if those libraries aren't present, the server won't be able to
use the RBD backend, but it will still be able to boot up and run.

### rbd client configuration
When using this backend, the client must set the "name" key to "rbd". In
addition, it must set the "pool" and "image" keys to specify which image
to use in a particular pool.

### rbd server configuration
To support this backend, the server must set the "ceph_conf" which specifies
the path of a Ceph configuration file, which is typically found in
"/etc/ceph/ceph.conf" and includes (among other things) the monitor hosts and
the needed keyrings to access the cluster. Additionally, the "ceph_user" key
must be set to specify the username to use when accessing the cluster.

## Example files
In the "examples" directory there are 2 files corresponding to the client and
server configuration to support an RBD-backed block device.
